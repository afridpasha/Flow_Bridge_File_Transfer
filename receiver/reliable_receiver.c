#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <unistd.h>

#define PORT 5555
#define BUF_SIZE 64000

// Helper function to receive exact number of bytes
int recv_exact(int sock, void *buffer, size_t length) {
    size_t received = 0;
    while (received < length) {
        int n = recv(sock, (char*)buffer + received, length - received, 0);
        if (n <= 0) return -1;
        received += n;
    }
    return received;
}

int main() {
    int s, client_s;
    struct sockaddr_in sin, client_addr;
    socklen_t client_len = sizeof(client_addr);
    char buf[BUF_SIZE];
    char filename[256];
    char size_buf[32];
    FILE *fp;
    long expected_size, total_bytes = 0;
    
    // Create socket
    if ((s = socket(PF_INET, SOCK_STREAM, 0)) < 0) {
        perror("socket");
        exit(1);
    }
    
    // Allow socket reuse
    int opt = 1;
    setsockopt(s, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));
    
    memset(&sin, 0, sizeof(sin));
    sin.sin_family = AF_INET;
    sin.sin_addr.s_addr = htonl(INADDR_ANY);
    sin.sin_port = htons(PORT);
    
    if (bind(s, (struct sockaddr*)&sin, sizeof(sin)) < 0) {
        perror("bind");
        exit(1);
    }
    
    if (listen(s, 5) < 0) {
        perror("listen");
        exit(1);
    }
    
    printf("✅ Reliable receiver ready on port %d\n", PORT);
    printf("📡 Accepting files from ANY IP address\n");
    printf("🌐 Local IP: "); fflush(stdout);
    system("hostname -I 2>/dev/null || echo 'Check with ifconfig'");
    
    while (1) {
        printf("\n⏳ Waiting for connection...\n");
        
        client_s = accept(s, (struct sockaddr*)&client_addr, &client_len);
        if (client_s < 0) {
            perror("accept");
            continue;
        }
        
        printf("🔗 Connected from %s\n", inet_ntoa(client_addr.sin_addr));
        
        // ===== NEW: Receive filename (fixed 256 bytes) =====
        if (recv_exact(client_s, filename, 256) < 0) {
            printf("❌ Error receiving filename\n");
            close(client_s);
            continue;
        }
        filename[255] = '\0'; // Ensure null termination
        
        // ===== NEW: Receive file size (fixed 20 bytes as string) =====
        if (recv_exact(client_s, size_buf, 20) < 0) {
            printf("❌ Error receiving file size\n");
            close(client_s);
            continue;
        }
        size_buf[20] = '\0';
        expected_size = atol(size_buf);
        
        printf("💾 Receiving: '%s' (expected size: %ld bytes)\n", filename, expected_size);
        
        // Open file for writing with received filename
        fp = fopen(filename, "wb");
        if (!fp) {
            perror("❌ Cannot create file");
            close(client_s);
            continue;
        }
        
        total_bytes = 0;
        
        // Receive file data
        while (total_bytes < expected_size) {
            int to_recv = (expected_size - total_bytes < BUF_SIZE) ? 
                          (expected_size - total_bytes) : BUF_SIZE;
            
            int len = recv(client_s, buf, to_recv, 0);
            if (len <= 0) {
                printf("❌ Connection closed prematurely\n");
                break;
            }
            
            size_t written = fwrite(buf, 1, len, fp);
            if (written != len) {
                printf("❌ Error writing to file!\n");
                break;
            }
            
            total_bytes += len;
            printf("📥 Received %d bytes (Total: %ld / %ld bytes - %.1f%%)\n", 
                   len, total_bytes, expected_size, 
                   (total_bytes * 100.0) / expected_size);
            
            fflush(fp);
        }
        
        fclose(fp);
        close(client_s);
        
        // Verify file integrity
        if (total_bytes == expected_size) {
            printf("✅ File transfer complete! Total: %ld bytes\n", total_bytes);
            printf("📁 File saved as: %s\n", filename);
            
            // Double-check file size on disk
            FILE *verify = fopen(filename, "rb");
            if (verify) {
                fseek(verify, 0, SEEK_END);
                long actual = ftell(verify);
                fclose(verify);
                
                if (actual == expected_size) {
                    printf("✓ File integrity verified (%ld bytes)\n", actual);
                } else {
                    printf("⚠️  Size mismatch! Expected %ld, got %ld\n", 
                           expected_size, actual);
                }
            }
        } else {
            printf("⚠️  Incomplete transfer! Received %ld of %ld bytes\n", 
                   total_bytes, expected_size);
        }
        
        printf("🔄 Ready for next transfer...\n");
    }
    
    close(s);
    return 0;
}