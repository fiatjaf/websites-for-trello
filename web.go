package main

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"github.com/gorilla/mux"
	"github.com/hoisie/redis"
	"io/ioutil"
	"log"
	"net/http"
	"net/url"
	"os"
)

var rabbitMQQueue string
var rabbitMQPublishURL string
var rds redis.Client

func main() {
	// setup globals
	p, err := url.Parse(os.Getenv("CLOUDAMQP_URL"))
	if err != nil {
		log.Fatal("couldn't parse CLOUDAMQP_URL.")
	}
	rabbitMQPublishURL = fmt.Sprintf("https://%s@%s/api/exchanges%s/amq.default/publish", p.User, p.Host, p.Path)
	rabbitMQQueue = "wft"
	if os.Getenv("DEBUG") != "" {
		rabbitMQQueue = "wft-test"
	}

	// connect to redis
	rds.Addr = os.Getenv("REDIS_HOST") + ":" + os.Getenv("REDIS_PORT")
	rds.Password = os.Getenv("REDIS_PASSWORD")
	rds.MaxPoolSize = 2

	// router
	r := mux.NewRouter()
	r.HandleFunc("/check", func(w http.ResponseWriter, r *http.Request) {
		// a handler for telling CHECKs and external monitors that this app is ok
		w.WriteHeader(http.StatusOK)
	})
	r.HandleFunc("/board", func(w http.ResponseWriter, r *http.Request) {
		// handling trello test request
		if r.Method == "GET" {
			log.Print(":: RECEIVE-WEBHOOKS :: trello checks this endpoint when creating a webhook.")
			w.WriteHeader(http.StatusOK)
			return
		}

		// handling trello POST
		// body is json
		log.Print(":: RECEIVE-WEBHOOKS :: got a trello message.")

		defer r.Body.Close()
		body, err := ioutil.ReadAll(r.Body)
		if err != nil {
			http.Error(w, "Your request is wrong.", 400)
			return
		}

		// if the board was reported as not existing, send a 410 so the webhooks stops showing
		var data struct {
			Model struct {
				Id string `json:"id"`
			} `json:"model"`
		}
		err = json.Unmarshal(body, &data)
		if err == nil {
			remove, err := rds.Srem("deleted-board", []byte(data.Model.Id))
			if err == nil && remove { // if the redis has failed we will not delete anything.
				log.Print(data.Model.Id + "is a deleted board. returning a 410 to delete this webhook.")
				w.WriteHeader(http.StatusGone)
				return
			}
		}

		// dispatch message to rabbitmq
		err = rabbitSend(body)
		if err != nil {
			log.Print(err.Error())
			http.Error(w, "Error handling message.", 500)
			return
		}
		w.WriteHeader(http.StatusOK)
	})
	r.HandleFunc("/webmention", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != "POST" {
			http.Error(w, "Your request is wrong.", 400)
			return
		}

		// webmention endpoint
		// body is x-www-form-urlencoded
		log.Print(":: RECEIVE-WEBHOOKS :: got a webmention.")

		source := r.FormValue("source")
		target := r.FormValue("target")
		webmention := struct {
			Type   string `json:"type"`
			Source string `json:"source"`
			Target string `json:"target"`
		}{
			Type:   "webmentionReceived",
			Source: source,
			Target: target,
		}
		if webmention.Source == "" || webmention.Target == "" {
			http.Error(w, "Your request is missing things.", 400)
			return
		}

		// make a json string
		webmentionMessage, err := json.Marshal(webmention)

		err = rabbitSend(webmentionMessage)
		if err != nil {
			log.Print(err.Error())
			http.Error(w, "Error handling message.", 500)
			return
		}
		w.WriteHeader(http.StatusOK)
	})

	port := os.Getenv("PORT")
	if port == "" {
		port = "5000"
	}
	log.Print(":: RECEIVE-WEBHOOKS :: listening at port " + port)
	http.ListenAndServe(":"+os.Getenv("PORT"), r)
}

func rabbitSend(payload []byte) error {
	data := struct {
		Payload         string            `json:"payload"`
		PayloadEncoding string            `json:"payload_encoding"`
		RoutingKey      string            `json:"routing_key"`
		Properties      map[string]string `json:"properties"`
	}{
		Payload:         string(payload),
		PayloadEncoding: "string",
		RoutingKey:      rabbitMQQueue,
		Properties:      make(map[string]string),
	}
	jsondata, _ := json.Marshal(data)
	jsondatabuffer := bytes.NewBuffer(jsondata)

	resp, err := http.Post(rabbitMQPublishURL, "application/json", jsondatabuffer)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	respstring, err := ioutil.ReadAll(resp.Body)
	if err != nil {
		return err
	}
	var reply struct {
		Routed bool `json:"routed"`
	}
	err = json.Unmarshal(respstring, &reply)
	if err != nil {
		return err
	}
	if !reply.Routed {
		return errors.New("Message wasn't routed.")
	}
	return nil
}
