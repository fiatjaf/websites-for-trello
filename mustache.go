package main

import (
	"github.com/jabley/mustache"
)

func renderOnTopOf(context BaseData, filenames ...string) string {
	for _, filename := range filenames {
		context.Content = mustache.RenderFile(filename, context)
	}
	return context.Content
}
