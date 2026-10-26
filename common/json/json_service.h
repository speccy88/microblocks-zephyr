/* SPDX-License-Identifier: MIT */
#ifndef MB_JSON_SERVICE_H
#define MB_JSON_SERVICE_H
#include <stddef.h>
#ifdef __cplusplus
extern "C" {
#endif
#define MB_JSON_MAX_BYTES 4096
#define MB_JSON_MAX_PATH 1024
#define MB_JSON_MAX_VALUES 128
#define MB_JSON_MAX_DEPTH 16
#define MB_JSON_ARENA_BYTES (96 * 1024)
typedef enum {
 MB_JSON_VALIDATE, MB_JSON_COMPACT, MB_JSON_GET, MB_JSON_TEXT,
 MB_JSON_TYPE, MB_JSON_LENGTH, MB_JSON_KEYS, MB_JSON_SET,
 MB_JSON_REMOVE, MB_JSON_APPEND, MB_JSON_QUOTE
} mb_json_op;
typedef enum {
 MB_JSON_OK, MB_JSON_INVALID, MB_JSON_LIMIT, MB_JSON_MEMORY,
 MB_JSON_DUPLICATE, MB_JSON_PATH, MB_JSON_MISSING, MB_JSON_WRONG_TYPE,
 MB_JSON_TEXT_NUL, MB_JSON_ROOT_REMOVE, MB_JSON_BAD_ARGUMENT
} mb_json_error;
/* No heap fallback. Distinct caller-owned arena/output; input is never mutated.
 * On failure output bytes are unchanged and *output_length is zero.
 * Caller serializes shared arena access and clears scratch after use. */
mb_json_error mb_json_run(mb_json_op op,
 const char *input, size_t input_length, const char *path, size_t path_length,
 const char *value, size_t value_length, void *arena, size_t arena_length,
 char *output, size_t output_capacity, size_t *output_length);
const char *mb_json_error_text(mb_json_error error);
/* SmallVM stores NUL-terminated strings padded to word boundaries. Reject
 * hidden nonzero bytes after a terminator instead of accepting a JSON prefix. */
mb_json_error mb_json_padded_text_length(const char *text,size_t capacity,size_t limit,size_t *length);
#ifdef __cplusplus
}
#endif
#endif
