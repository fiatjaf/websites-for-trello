package main

import (
	"net/http"

	log "github.com/Sirupsen/logrus"
	"github.com/gorilla/mux"
)

func index(w http.ResponseWriter, r *http.Request) {
	requestData := loadRequestData(r)
	parsePage(r, &requestData)
	countPageViews(requestData)
	// ~

	// fetch cards for home
	err := completeWithIndexCards(&requestData)
	if err != nil {
		log.WithFields(log.Fields{
			"context": requestData,
		}).Error("error getting index cards")
		http.Error(w, err.Error(), 500)
		return
	}

	err = render.ExecuteTemplate(w, "list", requestData)
	if err != nil {
		log.Print(err)
	}
}

func label(w http.ResponseWriter, r *http.Request) {
	requestData := loadRequestData(r)
	parsePage(r, &requestData)
	countPageViews(requestData)

	ppp := requestData.Prefs.PostsPerPage()
	labelSlug := mux.Vars(r)["label-slug"]

	// fetch home cards for this label
	var cards []Card
	err := db.Select(&cards, `
(
  SELECT slug,
         name,
         '' AS excerpt,
         null AS due,
         id,
         '""'::json AS users,
         0 AS pos,
         '' AS cover,
         '""'::jsonb AS attachments
  FROM labels
  WHERE board_id = $2
    AND slug = $3
    AND visible
) UNION ALL (
  SELECT cards.slug,
         cards.name,
         substring(cards.desc from 0 for $1) AS excerpt,
         cards.due,
         cards.id,
         array_to_json(array(SELECT row_to_json(u) FROM users AS u WHERE u._id = ANY(cards.users))) AS users,
         cards.pos,
         coalesce(cards.cover, '') AS cover,
         cards.attachments->'attachments' AS attachments
  FROM cards
  INNER JOIN labels
  ON labels.id = ANY(cards.labels)
  WHERE board_id = $2
    AND (labels.slug = $3 OR labels.id = $3)
    AND cards.visible
    AND labels.visible
  ORDER BY pos
  OFFSET $4
  LIMIT $5
)
ORDER BY pos
    `, requestData.Prefs.Excerpts(), requestData.Board.Id, labelSlug, ppp*(requestData.Page-1), ppp+1)
	if err != nil {
		if err.Error() == "sql: no rows in result set" {
			log.WithFields(log.Fields{
				"board": requestData.Board.Id,
				"label": labelSlug,
			}).Info("label not found.")
			error404(w, r)
			return
		} else {
			log.WithFields(log.Fields{
				"board": requestData.Board.Id,
				"label": labelSlug,
				"err":   err.Error(),
			}).Error("unknown error fetching label.")
			http.Error(w, "An unknown error has ocurred, we are sorry.", 500)
			return
		}
	}

	// we haven't found the requested label (when the label has 0 cards, we should get 1 here)
	if len(cards) < 1 {
		error404(w, r)
		return
	}

	// the first row is a Label dressed as a Card
	label := Label{
		Name:  cards[0].Name,
		Color: cards[0].Color,
		Slug:  cards[0].Slug,
	}
	cards = cards[1:]

	if len(cards) > ppp {
		requestData.HasNext = true
		cards = cards[:ppp]
	}

	requestData.Aggregator = label
	requestData.Cards = cards

	render.ExecuteTemplate(w, "list", requestData)
}

func card(w http.ResponseWriter, r *http.Request) {
	requestData := loadRequestData(r)
	countPageViews(requestData)

	vars := mux.Vars(r)
	listSlug := vars["list-slug"]
	cardSlug := vars["card-slug"]

	// fetch this card and its parent list
	var cards []Card
	err := db.Select(&cards, `
SELECT slug, name, due, id, "desc", attachments, checklists, labels, users, cover
FROM (
  (
    SELECT slug,
           name,
           null AS due,
           id,
           '' AS "desc",
           '""'::jsonb AS attachments,
           '""'::jsonb AS checklists,
           '""'::json AS labels,
           '""'::json AS users,
           0 AS sort,
           '' AS cover
    FROM lists
    WHERE board_id = $1
      AND slug = $2
      AND visible
    LIMIT 1
  ) UNION ALL (
    SELECT cards.slug,
           cards.name,
           cards.due,
           cards.id,
           cards.desc,
           cards.attachments->'attachments' AS attachments,
           cards.checklists->'checklists' AS checklists,
           array_to_json(array(SELECT row_to_json(l) FROM labels AS l WHERE l.id = ANY(cards.labels) AND l.visible)) AS labels,
           array_to_json(array(SELECT row_to_json(u) FROM users AS u WHERE u._id = ANY(cards.users))) AS users,
           1 AS sort,
           coalesce(cards.cover, '') AS cover
    FROM cards
    INNER JOIN lists
    ON lists.id = cards.list_id
    WHERE board_id = $1
      AND cards.slug = $3
      AND lists.slug = $2
      AND cards.visible
    GROUP BY cards.id
  )
) AS u
ORDER BY sort
	`, requestData.Board.Id, listSlug, cardSlug)
	if err != nil {
		if err.Error() == "sql: no rows in result set" {
			log.WithFields(log.Fields{
				"board": requestData.Board.Id,
				"list":  listSlug,
				"card":  cardSlug,
			}).Info("card not found.")
			error404(w, r)
			return
		} else {
			log.WithFields(log.Fields{
				"board": requestData.Board.Id,
				"list":  listSlug,
				"card":  cardSlug,
				"err":   err.Error(),
			}).Error("unknown error fetching card.")
			http.Error(w, "An unknown error has ocurred, we are sorry.", 500)
			return
		}
	}

	// we haven't found the requested list and card
	if len(cards) < 2 {
		error404(w, r)
		return
	}

	// the first row is a List dressed as a Card
	list := List{
		Name: cards[0].Name,
		Slug: cards[0].Slug,
	}
	requestData.Aggregator = list
	requestData.Card = cards[1]

	// comments
	if requestData.Prefs.Comments.Display && !requestData.Card.IsPage {
		var comments []Comment
		err := db.Select(&comments, `
SELECT id, author_url, author_name, body, source_display, source_url
FROM comments
WHERE card_id = $1
  AND body IS NOT NULL
ORDER BY id
    `, requestData.Card.Id)
		if err != nil {
			if err.Error() == "sql: no rows in result set" {
				log.WithFields(log.Fields{
					"card": requestData.Card.Id,
				}).Info("no comments were found")
			} else {
				log.WithFields(log.Fields{
					"card": requestData.Card.Id,
					"err":  err.Error(),
				}).Error("unknown error fetching comments.")
			}
		}
		requestData.Card.Comments = comments
	}

	err = render.ExecuteTemplate(w, "card", requestData)
	if err != nil {
		log.Print(err)
	}
}

func list(w http.ResponseWriter, r *http.Request) {
	requestData := loadRequestData(r)
	parsePage(r, &requestData)
	countPageViews(requestData)

	ppp := requestData.Prefs.PostsPerPage()
	listSlug := mux.Vars(r)["list-slug"]

	// fetch home cards for this list
	var cards []Card
	err := db.Select(&cards, `
(
  SELECT slug,
         name,
         '' AS excerpt,
         null AS due,
         id,
         '""'::json AS labels,
         '""'::json AS users,
         0 AS pos,
         '' AS cover,
         '""'::jsonb AS attachments
  FROM lists
  WHERE board_id = $2
    AND slug = $3
    AND visible
) UNION ALL (
  SELECT cards.slug,
         cards.name,
         substring(cards.desc from 0 for $1) AS excerpt,
         cards.due,
         cards.id,
         array_to_json(array(SELECT row_to_json(l) FROM labels AS l WHERE l.id = ANY(cards.labels) AND l.visible)) AS labels,
         array_to_json(array(SELECT row_to_json(u) FROM users AS u WHERE u._id = ANY(cards.users))) AS users,
         cards.pos,
         coalesce(cards.cover, '') AS cover,
         cards.attachments->'attachments' AS attachments
  FROM cards
  INNER JOIN lists
  ON lists.id = cards.list_id
  WHERE board_id = $2
    AND lists.slug = $3
    AND lists.visible
    AND cards.visible
  ORDER BY pos
  OFFSET $4
  LIMIT $5
)
ORDER BY pos
    `, requestData.Prefs.Excerpts(), requestData.Board.Id, listSlug, ppp*(requestData.Page-1), ppp+1)
	if err != nil {
		if err.Error() == "sql: no rows in result set" {
			log.WithFields(log.Fields{
				"board": requestData.Board.Id,
				"list":  listSlug,
			}).Info("list not found.")
			error404(w, r)
			return
		} else {
			log.WithFields(log.Fields{
				"board": requestData.Board.Id,
				"list":  listSlug,
				"err":   err.Error(),
			}).Error("unknown error fetching list.")
			http.Error(w, "An unknown error has ocurred, we are sorry.", 500)
			return
		}
	}

	// we haven't found the requested list (when the list has 0 cards, we should get 1 here)
	if len(cards) < 1 {
		error404(w, r)
		return
	}

	// the first row is a List dressed as a Card
	list := List{
		Name: cards[0].Name,
		Slug: cards[0].Slug,
	}
	cards = cards[1:]

	if len(cards) > ppp {
		requestData.HasNext = true
		cards = cards[:ppp]
	}

	requestData.Aggregator = list
	requestData.Cards = cards

	render.ExecuteTemplate(w, "list", requestData)
}
