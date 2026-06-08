/*
 * Standalone reproduce driver. Used when libFuzzer runtime is unavailable.
 * Reads a single input file (argv[1]) and feeds it to LLVMFuzzerTestOneInput,
 * so `./harness <blob>` behaves identically to libFuzzer's single-input replay.
 */
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>

int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size);

int main(int argc, char **argv) {
    if (argc < 2) {
        fprintf(stderr, "usage: %s <input-file>\n", argv[0]);
        return 2;
    }
    FILE *f = fopen(argv[1], "rb");
    if (!f) {
        perror("fopen");
        return 2;
    }
    fseek(f, 0, SEEK_END);
    long n = ftell(f);
    fseek(f, 0, SEEK_SET);
    if (n < 0) {
        fclose(f);
        return 2;
    }
    uint8_t *buf = (uint8_t *)malloc((size_t)n + 1);
    size_t got = fread(buf, 1, (size_t)n, f);
    fclose(f);
    LLVMFuzzerTestOneInput(buf, got);
    free(buf);
    return 0;
}
