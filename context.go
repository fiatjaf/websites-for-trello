package main

import (
	"github.com/gorilla/context"
	"net/http"
)

type key int

const k key = 23

func loadRequestData(r *http.Request) RequestData {
	if val := context.Get(r, k); val != nil {
		return val.(RequestData)
	}
	return RequestData{}
}

func saveRequestData(r *http.Request, requestData RequestData) {
	context.Set(r, k, requestData)
}

func clearContextMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		next.ServeHTTP(w, r)
		context.Clear(r) // clears after handling everything.
	})
}
