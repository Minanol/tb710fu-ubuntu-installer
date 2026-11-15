package main

import (
	"encoding/binary"
	"io"
	"net"
	"os"
	"testing"
)

func TestAllowedRemote(t *testing.T) {
	for _, tc := range []struct {
		input   string
		allowed bool
	}{
		{"172.16.42.1:1234", true},
		{"[::ffff:172.16.42.1]:1234", true},
		{"172.16.42.2:1234", false},
		{"192.168.1.1:1234", false},
		{"172.16.42.1", false},
		{"not-an-address", false},
	} {
		if got := allowedRemote(tc.input); got != tc.allowed {
			t.Errorf("allowedRemote(%q)=%v", tc.input, got)
		}
	}
}

func TestFlushFailureIsReported(t *testing.T) {
	f, err := os.CreateTemp(t.TempDir(), "nbd")
	if err != nil {
		t.Fatal(err)
	}
	if err := f.Close(); err != nil {
		t.Fatal(err)
	}
	im := &image{f: f, size: 4096}
	if im.flags()&flagTrim != 0 {
		t.Fatal("unsupported trim advertised")
	}
	s := &server{img: im, exports: map[string]bool{"arch": true}}
	client, peer := net.Pipe()
	defer client.Close()
	go s.serve(peer, "test")
	read := func(n int) []byte {
		b := make([]byte, n)
		if _, err := io.ReadFull(client, b); err != nil {
			t.Fatal(err)
		}
		return b
	}
	write := func(b []byte) {
		if _, err := client.Write(b); err != nil {
			t.Fatal(err)
		}
	}
	read(20)
	write(u32(0))
	header := append(u64(optsMagic), u32(optExportName)...)
	header = append(header, u32(4)...)
	header = append(header, []byte("arch")...)
	write(header)
	read(134)
	request := make([]byte, 28)
	binary.BigEndian.PutUint32(request[0:4], reqMagic)
	binary.BigEndian.PutUint16(request[6:8], cmdFlush)
	write(request)
	response := read(16)
	if got := binary.BigEndian.Uint32(response[4:8]); got != 5 {
		t.Fatalf("flush error=%d, want EIO", got)
	}
}
