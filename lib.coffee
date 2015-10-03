

userRequired = (request, response, next) ->
  if not request.session.user
    return response.sendStatus 401
  next()

module.exports =
  userRequired: userRequired
