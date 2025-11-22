#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <unistd.h>
#include <netdb.h>
#include <libgen.h>

#define BUF_SIZE 64000

int main(int argc, char *argv[]) {
    int s;
    struct sockaddr_in sin;
    char *target_host, *filename;
    char buf[BUF_SIZE];
    char send_filename[256];
    FILE *fp;
    long file_size;
    int port = 5555;  // Default port
    
    if (argc < 3 || argc > 4) {
        fprintf(stderr, "Usage: %s <host:port or host> <filename>\n", argv[0]);
        fprintf(stderr, "Examples:\n");
        fprintf(stderr, "  %s 10.147.17.100:5555 photo.png\n", argv[0]);
        fprintf(stderr, "  %s 192.168.1.10 photo.png (uses port 5555)\n", argv[0]);
        exit(1);
    }
    
    target_host = argv[1];
    filename = argv[2];
    
    // ===== NEW: Parse host:port format =====
    char *colon = strchr(target_host, ':');
    if (colon != NULL) {
        *colon = '\0';  // Split string at ':'
        port = atoi(colon + 1);
        if (port <= 0 || port > 65535) {
            fprintf(stderr, "❌ Invalid port number: %d\n", port);
            exit(1);
        }
    }
    
    // Open file and get size
    fp = fopen(filename, "rb");
    if (!fp) {
        printf("❌ File not found: %s\n", filename);
        exit(1);
    }
    fseek(fp, 0, SEEK_END);
    file_size = ftell(fp);
    fseek(fp, 0, SEEK_SET);
    
    // Create socket
    if ((s = socket(PF_INET, SOCK_STREAM, 0)) < 0) {
        perror("socket");
        fclose(fp);
        exit(1);
    }
    
    memset(&sin, 0, sizeof(sin));
    sin.sin_family = AF_INET;
    
    // Support both IP addresses and hostnames (including ZeroTier IPs)
    struct hostent *host_entry = gethostbyname(target_host);
    if (host_entry) {
        memcpy(&sin.sin_addr, host_entry->h_addr_list[0], host_entry->h_length);
    } else {
        sin.sin_addr.s_addr = inet_addr(target_host);
        if (sin.sin_addr.s_addr == INADDR_NONE) {
            fprintf(stderr, "❌ Invalid host: %s\n", target_host);
            fclose(fp);
            close(s);
            exit(1);
        }
    }
    sin.sin_port = htons(port);
    
    // Connect to receiver
    printf("🔌 Connecting to %s:%d...\n", target_host, port);
    if (connect(s, (struct sockaddr*)&sin, sizeof(sin)) < 0) {
        perror("❌ Connection failed");
        printf("💡 Make sure receiver and ZeroTier network are running!\n");
        fclose(fp);
        close(s);
        exit(1);
    }
    
    printf("✅ Connected to %s:%d\n", target_host, port);
    
    // Extract just the filename (no path)
    char *temp = strdup(filename);
    char *base = basename(temp);
    strncpy(send_filename, base, sizeof(send_filename) - 1);
    send_filename[sizeof(send_filename) - 1] = '\0';
    free(temp);
    
    // Send filename as fixed 256-byte field
    char filename_buf[256] = {0};
    strncpy(filename_buf, send_filename, sizeof(filename_buf) - 1);
    
    if (send(s, filename_buf, sizeof(filename_buf), 0) != sizeof(filename_buf)) {
        perror("send filename");
        fclose(fp);
        close(s);
        exit(1);
    }
    
    // Send file size as fixed 20-byte string
    char size_buf[32];
    snprintf(size_buf, sizeof(size_buf), "%020ld", file_size);
    
    if (send(s, size_buf, 20, 0) != 20) {
        perror("send size");
        fclose(fp);
        close(s);
        exit(1);
    }
    
    printf("📤 Sending %s (size: %ld bytes)...\n", send_filename, file_size);
    
    // Send file data
    int bytes_read, total_sent = 0;
    while ((bytes_read = fread(buf, 1, BUF_SIZE, fp)) > 0) {
        int sent = 0;
        // Ensure all bytes are sent (handle partial sends)
        while (sent < bytes_read) {
            int result = send(s, buf + sent, bytes_read - sent, 0);
            if (result < 0) {
                perror("send data");
                fclose(fp);
                close(s);
                exit(1);
            }
            sent += result;
        }
        
        total_sent += bytes_read;
        printf("📤 Sent %d bytes (Total: %d / %ld bytes - %.1f%%)\n", 
               bytes_read, total_sent, file_size, 
               (total_sent * 100.0) / file_size);
    }
    
    fclose(fp);
    close(s);
    
    if (total_sent == file_size) {
        printf("✅ File transfer complete! Total: %d bytes\n", total_sent);
    } else {
        printf("⚠️  Warning: Sent %d bytes but file was %ld bytes\n", total_sent, file_size);
    }
    
    return 0;
}