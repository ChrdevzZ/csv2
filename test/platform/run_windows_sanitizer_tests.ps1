[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)]
  [string] $BuildDirectory,

  [string] $Configuration = "Release",

  [string] $Label = "sanitizer-runtime",

  [string] $NameRegex = "",

  [Parameter(Mandatory = $true)]
  [string] $OutputJunit
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-TestProperty {
  param(
    [Parameter(Mandatory = $true)] $Test,
    [Parameter(Mandatory = $true)] [string] $Name
  )

  $property = @($Test.properties | Where-Object { $_.name -eq $Name })
  if ($property.Count -ne 1) {
    throw "CTest entry '$($Test.name)' must have exactly one $Name property"
  }
  return $property[0].value
}

function Write-JunitReport {
  param(
    [Parameter(Mandatory = $true)] [System.Collections.IEnumerable] $Results,
    [Parameter(Mandatory = $true)] [string] $Path
  )

  $items = @($Results)
  $failureCount = @($items | Where-Object { -not $_.Passed }).Count
  $totalSeconds = ($items | Measure-Object -Property Seconds -Sum).Sum
  if ($null -eq $totalSeconds) {
    $totalSeconds = 0.0
  }

  $absolutePath = [System.IO.Path]::GetFullPath($Path)
  $directory = [System.IO.Path]::GetDirectoryName($absolutePath)
  [System.IO.Directory]::CreateDirectory($directory) | Out-Null
  $temporaryPath = Join-Path $directory (
    ".{0}.{1}.tmp" -f [System.IO.Path]::GetFileName($absolutePath),
    [Guid]::NewGuid().ToString("N"))

  $settings = [System.Xml.XmlWriterSettings]::new()
  $settings.Encoding = [System.Text.UTF8Encoding]::new($false)
  $settings.Indent = $true
  $settings.NewLineChars = "`n"

  $writer = [System.Xml.XmlWriter]::Create($temporaryPath, $settings)
  try {
    $writer.WriteStartDocument()
    $writer.WriteStartElement("testsuite")
    $writer.WriteAttributeString("name", "csv2.windows.sanitizer")
    $writer.WriteAttributeString("tests", [string] $items.Count)
    $writer.WriteAttributeString("failures", [string] $failureCount)
    $writer.WriteAttributeString("errors", "0")
    $writer.WriteAttributeString("skipped", "0")
    $writer.WriteAttributeString(
      "time", $totalSeconds.ToString("0.000000", [Globalization.CultureInfo]::InvariantCulture))

    foreach ($result in $items) {
      $writer.WriteStartElement("testcase")
      $writer.WriteAttributeString("classname", "csv2.windows.sanitizer")
      $writer.WriteAttributeString("name", [string] $result.Name)
      $writer.WriteAttributeString(
        "time", $result.Seconds.ToString("0.000000", [Globalization.CultureInfo]::InvariantCulture))
      if (-not $result.Passed) {
        $writer.WriteStartElement("failure")
        $writer.WriteAttributeString("message", [string] $result.Message)
        $writer.WriteString([string] $result.Message)
        $writer.WriteEndElement()
      }
      $writer.WriteEndElement()
    }

    $writer.WriteEndElement()
    $writer.WriteEndDocument()
    $writer.Flush()
  }
  finally {
    $writer.Dispose()
  }

  try {
    [System.IO.File]::Move($temporaryPath, $absolutePath, $true)
  }
  finally {
    if ([System.IO.File]::Exists($temporaryPath)) {
      [System.IO.File]::Delete($temporaryPath)
    }
  }
}

$ctest = (Get-Command ctest.exe -ErrorAction Stop).Source
$resolvedBuild = (Resolve-Path -LiteralPath $BuildDirectory).Path
$manifestArguments = @(
  "--test-dir", $resolvedBuild,
  "-C", $Configuration,
  "-L", $Label,
  "--show-only=json-v1"
)
$manifestText = & $ctest @manifestArguments
if ($LASTEXITCODE -ne 0) {
  throw "CTest manifest query failed with exit code $LASTEXITCODE"
}
$manifest = $manifestText | ConvertFrom-Json
$tests = @($manifest.tests)
if ($NameRegex) {
  $tests = @($tests | Where-Object { $_.name -match $NameRegex })
}
if ($tests.Count -eq 0) {
  throw "CTest registered no matching sanitizer runtime tests"
}

$duplicateNames = @($tests | Group-Object name | Where-Object Count -ne 1)
if ($duplicateNames.Count -ne 0) {
  throw "CTest sanitizer manifest contains duplicate test names"
}
$benchmarkTests = @($tests | Where-Object { $_.name -like "csv2.benchmark.*" })
if ($benchmarkTests.Count -ne 0) {
  throw "Benchmark tests must not run under sanitizers"
}

$validated = foreach ($test in $tests) {
  $command = @($test.command)
  if ($command.Count -eq 0) {
    throw "Sanitizer test has no command: $($test.name)"
  }
  $executable = (Resolve-Path -LiteralPath $command[0]).Path
  if (-not [System.IO.File]::Exists($executable)) {
    throw "Sanitizer test executable does not exist: $($test.name)"
  }
  $workingDirectory = (Resolve-Path -LiteralPath (
      Get-TestProperty -Test $test -Name "WORKING_DIRECTORY")).Path
  $timeoutSeconds = [double] (Get-TestProperty -Test $test -Name "TIMEOUT")
  if (-not [double]::IsFinite($timeoutSeconds) -or $timeoutSeconds -le 0) {
    throw "Sanitizer test has an invalid timeout: $($test.name)"
  }
  [pscustomobject]@{
    Name = [string] $test.name
    Executable = $executable
    Arguments = @($command | Select-Object -Skip 1)
    WorkingDirectory = $workingDirectory
    TimeoutMilliseconds = [int] [Math]::Ceiling($timeoutSeconds * 1000.0)
  }
}

Write-Host "Running $($validated.Count) sanitizer tests from the CTest manifest"
$results = [Collections.Generic.List[object]]::new()
foreach ($test in $validated) {
  Write-Host "[ RUN      ] $($test.Name)"
  $startInfo = [Diagnostics.ProcessStartInfo]::new()
  $startInfo.FileName = $test.Executable
  $startInfo.WorkingDirectory = $test.WorkingDirectory
  $startInfo.UseShellExecute = $false
  foreach ($argument in $test.Arguments) {
    $startInfo.ArgumentList.Add([string] $argument)
  }

  $process = [Diagnostics.Process]::new()
  $process.StartInfo = $startInfo
  $watch = [Diagnostics.Stopwatch]::StartNew()
  $passed = $false
  $message = ""
  try {
    if (-not $process.Start()) {
      throw "process start returned false"
    }
    if (-not $process.WaitForExit($test.TimeoutMilliseconds)) {
      $process.Kill($true)
      $process.WaitForExit()
      $message = "timed out after $($test.TimeoutMilliseconds) ms"
    }
    elseif ($process.ExitCode -ne 0) {
      $message = "exited with code $($process.ExitCode)"
    }
    else {
      $passed = $true
    }
  }
  catch {
    $message = "failed to execute: $($_.Exception.Message)"
  }
  finally {
    $watch.Stop()
    $process.Dispose()
  }

  $results.Add([pscustomobject]@{
      Name = $test.Name
      Passed = $passed
      Message = $message
      Seconds = $watch.Elapsed.TotalSeconds
    })
  if ($passed) {
    Write-Host "[       OK ] $($test.Name)"
  }
  else {
    Write-Error "[  FAILED  ] $($test.Name): $message" -ErrorAction Continue
  }
}

Write-JunitReport -Results $results -Path $OutputJunit
$failed = @($results | Where-Object { -not $_.Passed })
if ($failed.Count -ne 0) {
  throw "$($failed.Count) sanitizer test(s) failed"
}
Write-Host "All $($results.Count) sanitizer tests passed"
