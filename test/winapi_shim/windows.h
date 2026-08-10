#pragma once

#include <cstddef>
#include <cstdint>

typedef void *HANDLE;
typedef std::uint32_t DWORD;
typedef int BOOL;
typedef std::size_t SIZE_T;

struct LARGE_INTEGER {
  std::int64_t QuadPart;
};

struct SYSTEM_INFO {
  DWORD dwAllocationGranularity;
};

#define INVALID_HANDLE_VALUE reinterpret_cast<HANDLE>(static_cast<std::intptr_t>(-1))
#define GENERIC_READ 0x80000000u
#define GENERIC_WRITE 0x40000000u
#define FILE_SHARE_READ 0x00000001u
#define FILE_SHARE_WRITE 0x00000002u
#define OPEN_EXISTING 3u
#define FILE_ATTRIBUTE_NORMAL 0x00000080u
#define PAGE_READONLY 0x00000002u
#define PAGE_READWRITE 0x00000004u
#define FILE_MAP_READ 0x00000004u
#define FILE_MAP_WRITE 0x00000002u
#define ERROR_ACCESS_DENIED 5u
#define ERROR_NOT_ENOUGH_MEMORY 8u
#define ERROR_FILE_INVALID 1006u

void GetSystemInfo(SYSTEM_INFO *system_info);
DWORD GetLastError();

HANDLE CreateFileA(const char *path, DWORD desired_access, DWORD share_mode,
                   void *security_attributes, DWORD creation_disposition,
                   DWORD flags_and_attributes, HANDLE template_file);
HANDLE CreateFileW(const wchar_t *path, DWORD desired_access, DWORD share_mode,
                   void *security_attributes, DWORD creation_disposition,
                   DWORD flags_and_attributes, HANDLE template_file);
BOOL GetFileSizeEx(HANDLE file, LARGE_INTEGER *file_size);
HANDLE CreateFileMapping(HANDLE file, void *attributes, DWORD protection,
                         DWORD maximum_size_high, DWORD maximum_size_low,
                         const char *name);
void *MapViewOfFile(HANDLE mapping, DWORD desired_access, DWORD offset_high,
                    DWORD offset_low, SIZE_T bytes_to_map);
BOOL CloseHandle(HANDLE handle);

BOOL FlushViewOfFile(const void *base_address, SIZE_T bytes_to_flush);
BOOL FlushFileBuffers(HANDLE file);
BOOL UnmapViewOfFile(const void *base_address);
