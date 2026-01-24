/* Simple test application for debugging */
#include <stdio.h>
#include <unistd.h>

int main() {
    int counter = 0;
    printf("Test app started (PID: %d)\n", getpid());

    while (1) {
        printf("Counter: %d\n", counter);
        counter++;
        sleep(1);
    }

    return 0;
}
