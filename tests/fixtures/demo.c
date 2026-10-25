/* SPDX-License-Identifier: MIT
 * Original RECON demo fixture. These functions are compiled, never executed by RECON.
 */
#define KEEP __attribute__((noinline,used))
KEEP unsigned int checksum_bytes(const unsigned char *data, unsigned long size) {
    unsigned int value = 5381;
    for (unsigned long i = 0; i < size; ++i) value = ((value << 5) + value) ^ data[i];
    return value;
}
KEEP int clamp_value(int value, int low, int high) {
    if (value < low) return low;
    if (value > high) return high;
    return value;
}
KEEP unsigned int count_bits(unsigned int value) {
    unsigned int count = 0;
    while (value) { value &= value - 1; ++count; }
    return count;
}
KEEP unsigned long string_length(const char *text) {
    unsigned long n = 0;
    while (text[n]) ++n;
    return n;
}
KEEP int find_value(const int *values, int count, int needle) {
    for (int i = 0; i < count; ++i) if (values[i] == needle) return i;
    return -1;
}
KEEP void reverse_bytes(unsigned char *data, unsigned long size) {
    for (unsigned long i = 0; i < size / 2; ++i) {
        unsigned char temp = data[i]; data[i] = data[size-i-1]; data[size-i-1] = temp;
    }
}
KEEP int sum_values(const int *data, int size) {
    int sum = 0;
    for (int i = 0; i < size; ++i) sum += data[i];
    return sum;
}
KEEP unsigned int greatest_common_divisor(unsigned int a, unsigned int b) {
    while (b) { unsigned int next = a % b; a = b; b = next; }
    return a;
}
KEEP void entry(void) { /* not a runnable userspace entry point */ }
