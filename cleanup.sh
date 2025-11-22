#!/bin/bash

echo "🧹 Cleaning up unnecessary files..."

# Remove old multicast files (not needed for direct IP transfer)
rm -f sender/server.c sender/station1.c sender/station2.c sender/sender.c
rm -f receiver/receiver.c receiver/client.c receiver/simple_receiver.c
rm -f receiver/compile_client.txt

# Remove compiled binaries (will recompile clean versions)
rm -f sender/server sender/station1 sender/direct_sender
rm -f receiver/receiver receiver/client receiver/simple_receiver receiver/direct_receiver

# Remove test/temporary files
rm -f receiver/received_file* sender/vid*.mp4 sender/test.*

echo "✅ Cleanup complete!"
echo "📁 Remaining essential files:"
echo "   - sender/reliable_sender.c (Universal file sender)"
echo "   - receiver/reliable_receiver.c (Universal file receiver)"
echo "   - README.md (Documentation)"

echo ""
echo "🔧 To compile and use:"
echo "   cd sender && gcc -o reliable_sender reliable_sender.c"
echo "   cd receiver && gcc -o reliable_receiver reliable_receiver.c"
echo ""
echo "📤 Send to any IP: ./reliable_sender TARGET_IP filename"
echo "📥 Receive from any IP: ./reliable_receiver"