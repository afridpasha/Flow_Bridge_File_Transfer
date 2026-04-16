// webrtc-transfer.js - Client-side WebRTC implementation

class WebRTCFileTransfer {
    constructor(signalingServerUrl, peerId) {
        this.signalingServerUrl = signalingServerUrl;
        this.peerConnection = null;
        this.dataChannel = null;
        
        // Use provided peerId or fallback to a new random one
        this.peerId = peerId || ('peer_' + Math.random().toString(36).substr(2, 9));
        this.remotePeerId = null;
        this.onFileReceived = null;
        this.onProgress = null;
        this.icePollingInterval = null;
        this.lastIceCandidateIndex = 0;
        
        // WebRTC configuration
        this.config = {
            iceServers: [
                { urls: 'stun:stun.l.google.com:19302' },
                { urls: 'stun:stun1.l.google.com:19302' },
                { urls: 'stun:stun2.l.google.com:19302' }
            ]
        };
    }
    
    async init() {
        // Register with signaling server
        console.log(`Initializing WebRTC with peer ID: ${this.peerId}`);
        const response = await fetch(`${this.signalingServerUrl}/register`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                peer_id: this.peerId,
                info: { browser: navigator.userAgent }
            })
        });
        
        if (!response.ok) {
            throw new Error(`Failed to register with signaling server: ${response.statusText}`);
        }
        
        return true;
    }
    
    async createOffer(remotePeerId) {
        this.remotePeerId = remotePeerId;
        this.lastIceCandidateIndex = 0;
        
        // Create peer connection
        this.peerConnection = new RTCPeerConnection(this.config);
        
        // Create data channel MUST be done before creating the offer
        this.dataChannel = this.peerConnection.createDataChannel('fileTransfer', {
            ordered: true
        });
        
        this.setupDataChannel();
        
        // Handle ICE candidates
        this.peerConnection.onicecandidate = (event) => {
            if (event.candidate) {
                this.sendIceCandidate(event.candidate);
            }
        };
        
        // Create offer
        const offer = await this.peerConnection.createOffer();
        await this.peerConnection.setLocalDescription(offer);
        
        // Send offer to signaling server
        await fetch(`${this.signalingServerUrl}/offer`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                from: this.peerId,
                to: remotePeerId,
                offer: offer
            })
        });
        
        console.log(`Sent offer to ${remotePeerId}`);
        
        // Stop any old polling, start fresh
        this.startIcePolling();
        
        // Wait for answer
        await this.waitForAnswer();
    }
    
    async acceptOffer(remotePeerId) {
        this.remotePeerId = remotePeerId;
        this.lastIceCandidateIndex = 0;
        
        console.log(`Trying to accept offer from ${remotePeerId}`);
        
        let offerData = null;
        for (let i = 0; i < 15; i++) {
            const response = await fetch(
                `${this.signalingServerUrl}/offer/${remotePeerId}/${this.peerId}`
            );
            
            if (response.ok) {
                offerData = await response.json();
                break;
            }
            // Wait 1 second before retrying
            await new Promise(resolve => setTimeout(resolve, 1000));
        }
        
        if (!offerData || !offerData.offer) {
            throw new Error('Sender has not sent an offer. Ensure the sender has initiated the connection.');
        }
        
        // Create peer connection
        this.peerConnection = new RTCPeerConnection(this.config);
        
        // Handle data channel
        this.peerConnection.ondatachannel = (event) => {
            this.dataChannel = event.channel;
            this.setupDataChannel();
        };
        
        // Handle ICE candidates
        this.peerConnection.onicecandidate = (event) => {
            if (event.candidate) {
                this.sendIceCandidate(event.candidate);
            }
        };
        
        // Set remote description
        await this.peerConnection.setRemoteDescription(offerData.offer);
        
        // Create answer
        const answer = await this.peerConnection.createAnswer();
        await this.peerConnection.setLocalDescription(answer);
        
        // Send answer to signaling server
        await fetch(`${this.signalingServerUrl}/answer`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                from: this.peerId,
                to: remotePeerId,
                answer: answer
            })
        });
        
        console.log(`Sent answer back to ${remotePeerId}`);
        
        // Stop any old polling, start fresh
        this.startIcePolling();
    }
    
    async waitForAnswer() {
        console.log("Waiting for receiver's answer...");
        // Poll for answer
        for (let i = 0; i < 30; i++) {
            await new Promise(resolve => setTimeout(resolve, 1000));
            
            const response = await fetch(
                `${this.signalingServerUrl}/answer/${this.remotePeerId}/${this.peerId}`
            );
            
            if (response.ok) {
                const data = await response.json();
                if (data.answer) {
                    await this.peerConnection.setRemoteDescription(data.answer);
                    console.log("Receiver's answer received and set!");
                    break;
                }
            }
        }
    }
    
    startIcePolling() {
        if (this.icePollingInterval) clearInterval(this.icePollingInterval);
        
        this.icePollingInterval = setInterval(async () => {
            if (!this.peerConnection || this.peerConnection.connectionState === 'closed') {
                clearInterval(this.icePollingInterval);
                return;
            }
            
            try {
                const response = await fetch(`${this.signalingServerUrl}/ice-candidates/${this.remotePeerId}`);
                if (response.ok) {
                    const data = await response.json();
                    const candidates = data.candidates || [];
                    
                    // Add only new candidates
                    for (let i = this.lastIceCandidateIndex; i < candidates.length; i++) {
                        if (this.peerConnection.remoteDescription) {
                            try {
                                await this.peerConnection.addIceCandidate(new RTCIceCandidate(candidates[i].candidate));
                            } catch (e) {
                                console.error('Error adding ICE candidate', e);
                            }
                        }
                    }
                    this.lastIceCandidateIndex = candidates.length;
                    
                    if (this.peerConnection.connectionState === 'connected' || 
                        this.peerConnection.connectionState === 'failed') {
                        clearInterval(this.icePollingInterval);
                        console.log("ICE polling stopped, connection state: " + this.peerConnection.connectionState);
                    }
                }
            } catch (e) {
                console.error('Error polling ICE candidates', e);
            }
        }, 2000);
    }
    
    setupDataChannel() {
        this.dataChannel.binaryType = 'arraybuffer'; // Crucial for chunk processing
        
        this.dataChannel.onopen = () => {
            console.log('Data channel opened');
        };
        
        this.dataChannel.onclose = () => {
            console.log('Data channel closed');
        };
        
        this.dataChannel.onmessage = (event) => {
            this.handleMessage(event.data);
        };
    }
    
    async sendFile(file) {
        if (!this.dataChannel || this.dataChannel.readyState !== 'open') {
            throw new Error('Data channel not ready');
        }
        
        // Send file metadata
        const metadata = {
            type: 'metadata',
            name: file.name,
            size: file.size,
            mimeType: file.type
        };
        this.dataChannel.send(JSON.stringify(metadata));
        console.log(`Sending file metadata: ${file.name} (${file.size} bytes)`);
        
        // Send file in chunks (128KB is safe and very performant on reliable connection)
        const chunkSize = 128 * 1024;
        const totalChunks = Math.ceil(file.size / chunkSize);
        
        for (let i = 0; i < totalChunks; i++) {
            const start = i * chunkSize;
            const end = Math.min(start + chunkSize, file.size);
            const chunk = file.slice(start, end);
            
            const arrayBuffer = await chunk.arrayBuffer();
            this.dataChannel.send(arrayBuffer);
            
            // Report progress periodically
            if (this.onProgress && (i % Math.ceil(totalChunks / 100) === 0 || i === totalChunks - 1)) {
                this.onProgress({
                    loaded: end,
                    total: file.size,
                    percent: (end / file.size * 100).toFixed(2)
                });
            }
            
            // Respect the buffer limits
            while (this.dataChannel.bufferedAmount > 8 * 1024 * 1024) {
                await new Promise(resolve => setTimeout(resolve, 50));
            }
        }
        
        // Send completion message
        this.dataChannel.send(JSON.stringify({ type: 'complete' }));
        console.log('File transmission complete.');
        return true;
    }
    
    handleMessage(data) {
        if (typeof data === 'string') {
            const message = JSON.parse(data);
            
            if (message.type === 'metadata') {
                console.log(`Receiving file metadata: ${message.name} (${message.size} bytes)`);
                this.receivingFile = {
                    name: message.name,
                    size: message.size,
                    mimeType: message.mimeType,
                    chunks: [],
                    receivedBytes: 0
                };
            } else if (message.type === 'complete') {
                this.completeFileReceive();
            }
        } else {
            // Binary data (file chunk)
            if (this.receivingFile) {
                this.receivingFile.chunks.push(data);
                this.receivingFile.receivedBytes += data.byteLength;
                
                if (this.onProgress && this.receivingFile.chunks.length % 50 === 0) {
                    this.onProgress({
                        loaded: this.receivingFile.receivedBytes,
                        total: this.receivingFile.size,
                        percent: (this.receivingFile.receivedBytes / this.receivingFile.size * 100).toFixed(2)
                    });
                }
            }
        }
    }
    
    completeFileReceive() {
        if (!this.receivingFile) return;
        
        console.log("Download complete, building final file.");
        
        // Update to 100%
        if (this.onProgress) {
            this.onProgress({
                loaded: this.receivingFile.size,
                total: this.receivingFile.size,
                percent: 100.00
            });
        }
        
        // Combine chunks
        const blob = new Blob(this.receivingFile.chunks, {
            type: this.receivingFile.mimeType
        });
        
        // Create file
        const file = new File([blob], this.receivingFile.name, {
            type: this.receivingFile.mimeType
        });
        
        if (this.onFileReceived) {
            this.onFileReceived(file);
        }
        
        this.receivingFile = null;
    }
    
    async sendIceCandidate(candidate) {
        try {
            await fetch(`${this.signalingServerUrl}/ice-candidate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    peer_id: this.peerId,
                    candidate: candidate
                })
            });
        } catch (e) {
            console.error('Failed to send ICE candidate', e);
        }
    }
    
    close() {
        if (this.icePollingInterval) clearInterval(this.icePollingInterval);
        if (this.dataChannel) {
            this.dataChannel.close();
        }
        if (this.peerConnection) {
            this.peerConnection.close();
        }
    }
}

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = WebRTCFileTransfer;
} else {
    window.WebRTCFileTransfer = WebRTCFileTransfer;
}
