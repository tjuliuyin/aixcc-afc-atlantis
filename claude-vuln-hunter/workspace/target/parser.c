/*
 * Deliberately vulnerable demo target (mirrors an OSS-Fuzz style project).
 * The fuzz harness (workspace/harness/harness.c) feeds attacker bytes into
 * parse_record(). There is a classic heap-buffer-overflow gated behind a
 * magic-byte "key condition", exactly the shape Atlantis' BCDA looks for.
 */
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include "parser.h"

/* Returns 0 on success, -1 on malformed input. */
int parse_record(const uint8_t *data, size_t size) {
    /* key condition 1: need at least header + length byte */
    if (size < 5) {
        return -1;
    }
    /* key condition 2: magic "FUZZ" must match */
    if (!(data[0] == 'F' && data[1] == 'U' && data[2] == 'Z' && data[3] == 'Z')) {
        return -1;
    }

    uint8_t declared_len = data[4];        /* attacker-controlled length */
    const uint8_t *payload = data + 5;
    size_t avail = size - 5;

    char *buf = (char *)malloc(16);        /* fixed 16-byte heap buffer */
    if (!buf) {
        return -1;
    }

    /* BUG: declared_len can exceed 16 -> heap-buffer-overflow (ASAN).
     * Also reads past `payload` if declared_len > avail. */
    memcpy(buf, payload, declared_len);

    int result = buf[0];                   /* force use so it isn't optimized out */
    free(buf);
    return result == 0 ? 0 : 1;
}
