package main

import (
	"crypto/subtle"
	"encoding/json"
	"io"
	"log"
	"net/http"
	"os"
	"strings"
	"sync"
	"time"
)

const (
	listenAddr = "127.0.0.1:28262"
	usersFile  = "/etc/hysteria/users.json"
	cacheTTL   = 5 * time.Second
)

type User struct {
	Password            string `json:"password"`
	MaxDownloadBytes    int64  `json:"max_download_bytes"`
	ExpirationDays      int    `json:"expiration_days"`
	AccountCreationDate string `json:"account_creation_date"`
	Blocked             bool   `json:"blocked"`
	UploadBytes         int64  `json:"upload_bytes"`
	DownloadBytes       int64  `json:"download_bytes"`
	UnlimitedUser       bool   `json:"unlimited_user"`
}

type httpAuthRequest struct {
	Addr string `json:"addr"`
	Auth string `json:"auth"`
	Tx   uint64 `json:"tx"`
}

type httpAuthResponse struct {
	OK bool   `json:"ok"`
	ID string `json:"id"`
}

var (
	userCache  map[string]User
	cacheMutex = &sync.RWMutex{}
)

func loadUsersToCache() {
	data, err := os.ReadFile(usersFile)
	if err != nil {
		return
	}
	var users map[string]User
	if err := json.Unmarshal(data, &users); err != nil {
		return
	}
	cacheMutex.Lock()
	userCache = users
	cacheMutex.Unlock()
}

func authHandler(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var req httpAuthRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid request", http.StatusBadRequest)
		return
	}

	username, password, ok := strings.Cut(req.Auth, ":")
	if !ok {
		json.NewEncoder(w).Encode(httpAuthResponse{OK: false})
		return
	}

	cacheMutex.RLock()
	user, ok := userCache[username]
	cacheMutex.RUnlock()

	// 1. Check existence
	if !ok {
		json.NewEncoder(w).Encode(httpAuthResponse{OK: false})
		return
	}

	// 2. Check if blocked
	if user.Blocked {
		json.NewEncoder(w).Encode(httpAuthResponse{OK: false})
		return
	}

	// 3. Check password (constant time)
	if subtle.ConstantTimeCompare([]byte(user.Password), []byte(password)) != 1 {
		time.Sleep(5 * time.Second) // Slow down brute-force attacks
		json.NewEncoder(w).Encode(httpAuthResponse{OK: false})
		return
	}

	// 4. Check if unlimited (if so, grant access)
	if user.UnlimitedUser {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(httpAuthResponse{OK: true, ID: username})
		return
	}

	// 5. Check expiration
	if user.ExpirationDays > 0 {
		creationDate, err := time.Parse("2006-01-02", user.AccountCreationDate)
		if err == nil && time.Now().After(creationDate.AddDate(0, 0, user.ExpirationDays)) {
			json.NewEncoder(w).Encode(httpAuthResponse{OK: false})
			return
		}
	}

	// 6. Check traffic limit
	if user.MaxDownloadBytes > 0 && (user.DownloadBytes+user.UploadBytes) >= user.MaxDownloadBytes {
		json.NewEncoder(w).Encode(httpAuthResponse{OK: false})
		return
	}

	// All checks passed
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(httpAuthResponse{OK: true, ID: username})
}

func main() {
	log.SetOutput(io.Discard) // Disable logging for max performance
	loadUsersToCache()

	ticker := time.NewTicker(cacheTTL)
	go func() {
		for range ticker.C {
			loadUsersToCache()
		}
	}()

	http.HandleFunc("/auth", authHandler)
	if err := http.ListenAndServe(listenAddr, nil); err != nil {
		// If we can't start, log to stderr so systemd can see it
		log.SetOutput(os.Stderr)
		log.Fatalf("Failed to start server: %v", err)
	}
}
