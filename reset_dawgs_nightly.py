from firebase import firebase
firebase = firebase.FirebaseApplication('https://tunedog.firebaseio.com', None)
result = firebase.get('/Dogs', None)
#firebase.post('/test',"new_user")
for key in result.keys():
    firebase.put('/Dogs/' + key, 'IsHere', 'nil')
  # data fix
  # if (key == "Data"):
  #   continue
  # firebase.put('/' + key,"Status","No Status Today")

