class VoiceRecorder {
  constructor() {
    this.mediaRecorder = null;
    this.audioChunks = [];
    this.stream = null;
    this.isRecording = false;
    this.recordingStartTime = null;
    this.maxRecordingTime = 15000; // 15 seconds in milliseconds
    this.recordingTimer = null;

    this.initializeElements();
    this.setupEventListeners();
  }

  initializeElements() {
    this.startButton = document.getElementById("startButton");
    this.loginButton = document.getElementById("loginButton");
    this.createAccountButton = document.getElementById("createAccountButton");
    this.logoutButton = document.getElementById("logoutButton");
    this.usernameInput = document.getElementById("usernameText");
    this.passwordInput = document.getElementById("passwordText");
  }

  setupEventListeners() {
    this.startButton.addEventListener("click", () => this.startRecording());
    this.loginButton.addEventListener("click", () => this.handleLogin());
    this.createAccountButton.addEventListener("click", () =>
      this.createAccount(),
    );
    this.logoutButton.addEventListener("click", () => this.handleLogout());
  }

  async startRecording() {
    try {
      // Request microphone access
      this.stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1, // Mono
          sampleRate: 44100, // 44.1 kHz
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });

      // create MediaRecorder webm WebM format
      const options = {
        mimeType: "audio/webm;codecs=opus",
      };

      // fallback if webm with opus is not supported
      if (!MediaRecorder.isTypeSupported(options.mimeType)) {
        options.mimeType = "audio/webm";
      }

      // the final fallback (do do doo do)
      if (!MediaRecorder.isTypeSupported(options.mimeType)) {
        options.mimeType = "";
      }

      this.mediaRecorder = new MediaRecorder(this.stream, options);
      this.audioChunks = [];

      this.mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          this.audioChunks.push(event.data);
        }
      };

      this.mediaRecorder.onstop = () => {
        this.processRecording();
      };

      this.mediaRecorder.onerror = (event) => {
        console.error("MediaRecorder error:", event.error);
        alert("Recording error: " + event.error.message);
        this.resetUI();
      };

      // Start recording
      this.mediaRecorder.start(1000); // Collect data every second
      this.isRecording = true;
      this.recordingStartTime = Date.now();

      this.startButton.disabled = true;
      this.startButton.textContent = `Recording... (${Math.floor(this.maxRecordingTime / 1000)}s left)`;

      this.updateRecordingTimer();

      setTimeout(() => {
        if (this.isRecording) {
          this.stopRecording();
        }
      }, this.maxRecordingTime);
    } catch (error) {
      console.error("Error starting recording:", error);
      alert("Could not access microphone: " + error.message);
      this.resetUI();
    }
  }

  stopRecording() {
    if (this.mediaRecorder && this.isRecording) {
      this.mediaRecorder.stop();
      this.isRecording = false;
      this.startButton.textContent = "Done recording!";

      if (this.stream) {
        this.stream.getTracks().forEach((track) => track.stop());
      }

      if (this.recordingTimer) {
        clearInterval(this.recordingTimer);
      }
    }
  }

  updateRecordingTimer() {
    this.recordingTimer = setInterval(() => {
      if (this.isRecording && this.recordingStartTime) {
        const elapsed = Date.now() - this.recordingStartTime;
        const seconds = Math.floor(elapsed / 1000);
        const remaining = Math.max(
          0,
          Math.floor(this.maxRecordingTime / 1000) - seconds,
        );
        this.startButton.textContent = `Recording... (${remaining}s left)`;
      }
    }, 1000);
  }

  async processRecording() {
    try {
      const audioBlob = new Blob(this.audioChunks, { type: "audio/webm" });

      if (audioBlob.size === 0) {
        throw new Error("No audio data recorded");
      }

      console.log(
        `Recorded audio blob: ${audioBlob.size} bytes, type: ${audioBlob.type}`,
      );

      const base64Audio = await this.blobToBase64(audioBlob);

      this.lastRecording = base64Audio;
      this.resetUI();
    } catch (error) {
      console.error("Error processing recording:", error);
      alert("Error processing recording: " + error.message);
      this.resetUI();
    }
  }

  async blobToBase64(blob) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => {
        // Remove the data URL prefix (e.g., "data:audio/webm;base64,")
        const base64 = reader.result.split(",")[1];
        resolve(base64);
      };
      reader.onerror = reject;
      reader.readAsDataURL(blob);
    });
  }

  async handleLogin() {
    const username = this.usernameInput.value.trim();
    const password = this.passwordInput.value.trim();

    if (!username || !password) {
      alert("Please enter both username and password");
      return;
    }

    if (!this.lastRecording) {
      alert("Please record audio first before logging in");
      return;
    }

    try {
      this.loginButton.disabled = true;
      this.loginButton.textContent = "Logging in...";

      const response = await fetch("/account/login", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          username: username,
          password: password,
          audio_data: this.lastRecording,
        }),
      });

      if (response.ok) {
        // the server should always return json with similarity
        let similarity = Math.round((await response.json()).similarity * 100);
        alert(`Login successful! Similarity: ${similarity}%`);
        // Login done
        // litestar middleware automatically sets session cookie
      } else {
        const responseText = await response.text();
        alert("Login failed: " + responseText);
      }
    } catch (error) {
      console.error("Login error:", error);
      alert("Login error: " + error.message);
    } finally {
      this.loginButton.disabled = false;
      this.loginButton.textContent = "Login";
    }
  }

  async handleLogout() {
    try {
      const response = await fetch("/account/logout", {
        method: "POST",
      });
      if (!response.ok) {
        const responseText = await response.text();
        throw new Error(responseText || "Logout failed");
      }
      alert("Logged out!");
    } catch (error) {
      console.error("Logout error:", error);
      alert("Logout error: " + error.message);
    }
  }

  async createAccount() {
    const username = this.usernameInput.value.trim();
    const password = this.passwordInput.value.trim();

    if (!username || !password) {
      alert("Please enter both username and password");
      return;
    }

    if (!this.lastRecording) {
      alert("Please record audio first before creating account");
      return;
    }

    try {
      const response = await fetch("/account/create", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          username: username,
          password: password,
          audio_data: this.lastRecording,
        }),
      });

      const responseText = await response.text();

      if (response.ok) {
        alert("Account created successfully!");
      } else {
        alert("Account creation failed: " + responseText);
      }
    } catch (error) {
      console.error("Account creation error:", error);
      alert("Account creation error: " + error.message);
    }
  }

  resetUI() {
    this.startButton.disabled = false;
    this.startButton.textContent = "Start Recognition";

    if (this.recordingTimer) {
      clearInterval(this.recordingTimer);
      this.recordingTimer = null;
    }
  }
}

// Initialize when DOM is loaded
document.addEventListener("DOMContentLoaded", () => {
  const recorder = new VoiceRecorder();

  window.voiceRecorder = recorder;
});
