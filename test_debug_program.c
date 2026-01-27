#include <stdio.h>
#include <unistd.h>

int add(int a, int b) {
    int result = a + b;
    return result;
}

int multiply(int x, int y) {
    int product = x * y;
    return product;
}

int main() {
    printf("Starting debug test program\n");

    int num1 = 5;
    int num2 = 10;

    int sum = add(num1, num2);
    printf("Sum: %d\n", sum);

    int product = multiply(num1, num2);
    printf("Product: %d\n", product);

    printf("Sleeping for a moment...\n");
    sleep(1);

    printf("Program complete\n");
    return 0;
}
