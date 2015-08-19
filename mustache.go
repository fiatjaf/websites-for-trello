package main

import (
	"github.com/jabley/mustache"
)

func renderOnTopOf(requestData RequestData, filenames ...string) string {
	for _, filename := range filenames {
		requestData.Content = mustache.RenderFile(filename, requestData)
	}
	return requestData.Content
}
