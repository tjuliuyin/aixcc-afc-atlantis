#ifndef PARSER_H
#define PARSER_H
#include <stdint.h>
#include <stddef.h>

/* Parse one attacker-supplied record. See parser.c for the vuln. */
int parse_record(const uint8_t *data, size_t size);

#endif /* PARSER_H */
