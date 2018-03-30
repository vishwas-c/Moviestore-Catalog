from flask import Flask, render_template, request, redirect, jsonify, url_for, flash
from sqlalchemy import create_engine, asc
from sqlalchemy.orm import sessionmaker
from database_setup import Base, Movies_Genre, Movies_name, User
from flask import session as login_session
import random
import string

from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import FlowExchangeError
import httplib2
import json
from flask import make_response
import requests

app = Flask(__name__)

CLIENT_ID = json.loads(
    open('client_secrets.json', 'r').read())['web']['client_id']
APPLICATION_NAME = "Movies Store Application"

# Connect to Database and create database session
engine = create_engine('sqlite:///movieslist.db') 
Base.metadata.bind = engine

DBSession = sessionmaker(bind=engine)
session = DBSession()

#LOGIN 
# Create anti-forgery token
@app.route('/login')
def showLogin():
    state = ''.join(random.choice(string.ascii_uppercase + string.digits) for x in xrange(32))
    login_session['state'] = state
    return render_template('login.html', STATE=state)

#FB Login
@app.route('/fbconnect', methods=['POST'])
def fbconnect():
    if request.args.get('state') != login_session['state']:
        response = make_response(json.dumps('Invalid state parameter.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    access_token = request.data
    print( "access token received %s " % access_token)


    app_id = json.loads(open('fb_client_secrets.json', 'r').read())['web']['app_id']
    app_secret = json.loads(
        open('fb_client_secrets.json', 'r').read())['web']['app_secret']
    url = 'https://graph.facebook.com/oauth/access_token?grant_type=fb_exchange_token&client_id=%s&client_secret=%s&fb_exchange_token=%s' % (
        app_id, app_secret, access_token)
    h = httplib2.Http()
    result = h.request(url, 'GET')[1]


    # Use token to get user info from API
    userinfo_url = "https://graph.facebook.com/v2.8/me"
    #Split Token to get req key
    token = result.split("&")[0]
    
    url = 'https://graph.facebook.com/v2.8/me?fields=id%2Cname%2Cemail%2Cpicture&access_token=' + access_token
    h = httplib2.Http()
    result = h.request(url, 'GET')[1]
    data = json.loads(result)
    login_session['provider'] = 'facebook'
    login_session['username'] = data["name"]
    login_session['email'] = data["email"]
    login_session['facebook_id'] = data["id"]

    # The token must be stored in the login_session in order to properly logout
    login_session['access_token'] = access_token #check

    # Get user picture  
    login_session['picture'] = data["data"]["url"]

    # see if user exists
    user_id = getUserID(login_session['email'])
    if not user_id:
        user_id = createUser(login_session)
    login_session['user_id'] = user_id

    output = ''
    output += '<h1>Hey there! Welcome, '
    output += login_session['username']

    output += '!</h1>'
    output += '<img src="'
    output += login_session['picture']
    output += ' " style = "width: 300px; height: 300px;border-radius: 150px;-webkit-border-radius: 150px;-moz-border-radius: 150px;"> '

    flash("Now logged in as %s" % login_session['username'],'success')
    return output

#FB Disconnect
@app.route('/fbdisconnect')
def fbdisconnect():
    facebook_id = login_session['facebook_id']
    # The access token must me included to successfully logout
    access_token = login_session['access_token']
    url = 'https://graph.facebook.com/%s/permissions?access_token=%s' % (facebook_id,access_token)
    h = httplib2.Http()
    result = h.request(url, 'DELETE')[1]
    return "you are now logged out"

#Google Login
@app.route('/gconnect', methods=['POST'])
def gconnect():
    # Validate state token
    if request.args.get('state') != login_session['state']:
        response = make_response(json.dumps('Invalid state parameter.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    # Obtain authorization code
    code = request.data

    try:
        # Upgrade the authorization code into a credentials object
        oauth_flow = flow_from_clientsecrets('client_secrets.json', scope='')
        oauth_flow.redirect_uri = 'postmessage'
        credentials = oauth_flow.step2_exchange(code)
    except FlowExchangeError:
        response = make_response(
            json.dumps('Failed to upgrade the authorization code.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Check that the access token is valid.
    access_token = credentials.access_token
    url = ('https://www.googleapis.com/oauth2/v1/tokeninfo?access_token=%s'
           % access_token)
    h = httplib2.Http()
    result = json.loads(h.request(url, 'GET')[1])
    # If there was an error in the access token info, abort.
    if result.get('error') is not None:
        response = make_response(json.dumps(result.get('error')), 500)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is used for the intended user.
    gplus_id = credentials.id_token['sub']
    if result['user_id'] != gplus_id:
        response = make_response(
            json.dumps("Token's user ID doesn't match given user ID."), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is valid for this app.
    if result['issued_to'] != CLIENT_ID:
        response = make_response(
            json.dumps("Token's client ID does not match app's."), 401)
        print ("Token's client ID does not match app's.")
        response.headers['Content-Type'] = 'application/json'
        return response

    stored_access_token = login_session.get('access_token') #Check
    stored_gplus_id = login_session.get('gplus_id')
    if stored_access_token is not None and gplus_id == stored_gplus_id:
        response = make_response(json.dumps('Current user is already connected.'),200)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Store the access token in the session for later use.
    login_session['access_token'] = credentials.access_token  #check
    login_session['gplus_id'] = gplus_id

    # Get user info
    userinfo_url = "https://www.googleapis.com/oauth2/v1/userinfo"
    params = {'access_token': credentials.access_token, 'alt': 'json'}
    answer = requests.get(userinfo_url, params=params)

    data = answer.json()

    login_session['username'] = data['name']
    login_session['picture'] = data['picture']
    login_session['email'] = data['email']
    login_session['provider'] = 'google'

    # see if user exists, if it doesn't make a new one
    user_id = getUserID(data["email"])
    if not user_id:
        user_id = createUser(login_session)
    login_session['user_id'] = user_id

    output = ''
    output += '<h1>Hey there! Welcome, '
    output += login_session['username']
    output += '!</h1>'
    output += '<img src="'
    output += login_session['picture']
    output += ' " style = "width: 30px; height: 30px;border-radius: 150px;-webkit-border-radius: 150px;-moz-border-radius: 150px;"> '
    flash("you are now logged in as %s" % login_session['username'],'Success!')
    print ("done!") 
    return output

#Google Disconnect

@app.route('/gdisconnect')
def gdisconnect():
    # Only disconnect a connected user.
    access_token = login_session.get('access_token')  
    if access_token is None:
        response = make_response(
            json.dumps('Current user not connected.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    #HTTP Get request to revoke back token
    url = 'https://accounts.google.com/o/oauth2/revoke?token=%s' % access_token
    h = httplib2.Http()
    result = h.request(url, 'GET')[0]

    if result['status'] == '200':
        response = make_response(json.dumps('Successfully disconnected.'), 200)
        response.headers['Content-Type'] = 'application/json'
        return response
    else:
        response = make_response(json.dumps('Failed to revoke token for given user.'), 400)
        response.headers['Content-Type'] = 'application/json'
        return response

# User Helper Functions

def createUser(login_session):
    newUser = User(name=login_session['username'],
                   email=login_session['email'],
                   picture=login_session['picture'])
    session.add(newUser)
    session.commit()
    user = session.query(User).filter_by(email=login_session['email']).one()
    return user.id


def getUserInfo(user_id):
    user = session.query(User).filter_by(id=user_id).one()
    return user


def getUserID(email):
    try:
        user = session.query(User).filter_by(email=email).one()
        return user.id
    except:
        return None

# JSON APIs to view Restaurant Information
@app.route('/api/v1/catalog.json') 
def showMoviesJSON():
    """returns JSON of all movies in Catalog"""
    items = session.query(Movies_name).order_by(Movies_name.id.desc())
    return jsonify(Movies_Names=[i.serialize for i in items ])


@app.route('/api/v1/genres/<int:genre_id>/movies/<int:movies_name_id>/JSON')
def singleMovieJSON(genre_id, movies_name_id):
    """Returns JSON Of selected Movie"""
    Movie_name = session.query(Movies_name).filter_by(id=movies_name_id).one()
    return jsonify(Movie_name=Movie_name.serialize)


@app.route('/api/v1/genres/JSON')
def genresJSON():
    """Returns JSON of all genres"""
    genres = session.query(Movies_Genre).all()
    return jsonify(Genres=[r.serialize for r in genres])

#CRUD Operations

# Homepage
# Show all genres and movies
@app.route('/')
@app.route('/genres/')
def showGenres():
    """Returns catalog page with all genres and recently added movies"""
    genres = session.query(Movies_Genre).all()
    items = session.query(Movies_name).order_by(Movies_name.id.desc())
    quantity = items.count()
    if 'username' not in login_session:
        return render_template('publicGenres.html',genres=genres, items=items,quantity=quantity)
    else:
        return render_template('genres.html',genres=genres, items=items,quantity=quantity)

# Create a new genre

@app.route('/genres/new/', methods=['GET', 'POST'])
def newGenres():
    if 'username' not in login_session:
        return redirect('/login')
    if request.method == 'POST':
        newGenres = Movies_Genre(
            name=request.form['name'], 
            user_id=login_session['user_id'])
        session.add(newGenres)
        flash('New Genre Successfully Created')
        session.commit()
        return redirect(url_for('showGenres'))
    else:
        return render_template('newGenres.html')

# Edit a genre


@app.route('/genres/<int:genre_id>/edit/', methods=['GET', 'POST'])
def editGenres(genre_id):
    if 'username' not in login_session:
        return redirect('/login')
    """Allows user to edit an existing genre"""
    editedGenres = session.query(
        Movies_Genre).filter_by(id=genre_id).one()
    if editedGenres.user_id != login_session['user_id']:
        return "<script>function myFunction() {alert('You are not authorized to edit this Genre. Please create your own Genre in order to edit.');}</script><body onload='myFunction()'>"
    if request.method == 'POST':
        if request.form['name']:
            editedGenres.name = request.form['name']
            flash('Genre Successfully Edited %s' % editedGenres.name,'success')
            return redirect(url_for('showGenres'))
    else:
        return render_template('editGenre.html', genre=editedGenres)


# Delete a genre
@app.route('/genres/<int:genre_id>/delete/', methods=['GET', 'POST'])
def deleteGenres(genre_id):
    if 'username' not in login_session:
        return redirect('/login')
    """Users can delete an existing genre"""
    genreToDelete = session.query(
        Movies_Genre).filter_by(id=genre_id).one()
    if genreToDelete.user_id != login_session['user_id']:
        return "<script>function myFunction() {alert('You are not authorized to delete this Genre. Please create your own Genre in order to delete.');}</script><body onload='myFunction()'>"
    if request.method == 'POST':
        session.delete(genreToDelete)
        flash('%s Successfully Deleted' % genreToDelete.name,'success')
        session.commit()
        return redirect(url_for('showGenres', genre_id=genre_id))
    else:
        return render_template('deleteGenre.html', genre=genreToDelete)

# CRUD operations for movie

# Show genre movies
@app.route('/genres/<int:genre_id>/')
@app.route('/genres/<int:genre_id>/movies/')
def showGenreMovies(genre_id):
    """Show movies in the genre"""
    genre = session.query(Movies_Genre).filter_by(id=genre_id).one()
    genres = session.query(Movies_Genre).all()
    creator = getUserInfo(Movies_Genre.user_id)   #check
    items = session.query(Movies_name).filter_by(
        genre_id=genre_id).order_by(Movies_name.id.desc())
    quantity=items.count()
    if 'username' not in login_session or creator.id != login_session['user_id']:
        return render_template('publicMovies.html', genre=genre, genres=genres ,items=items,quantity=quantity, creator=creator)
    else:
        return render_template('showMovie.html', genre=genre, genres=genres ,items=items,quantity=quantity, creator=creator)

#READ Movie - selecting specific movie show specific information about that movie
@app.route('/genres/<int:genre_id>/movies/<int:movies_name_id>/')
def showMovieItem(genre_id, movies_name_id):
    """returns movie item"""
    genre = session.query(Movies_Genre).filter_by(id=genre_id).one()
    item = session.query(
        Movies_name).filter_by(id=movies_name_id).one()
    creator = getUserInfo(genre.user_id)
    return render_template('genre_movie_name.html',genre=genre,item=item,creator=creator)

# Create a new movie
@app.route('/genres/movies/new/', methods=['GET', 'POST'])
def newMovie():
    if 'username' not in login_session:
        return redirect('/login')
    genres = session.query(Movies_Genre).all()
    if request.method == 'POST':
        addNewMovie = Movies_name(
            name=request.form['name'],
            description=request.form['description'],
            price=request.form['price'],
            year=request.form['year'], 
            genre_id=request.form['genre'] ,
            user_id=login_session['user_id'])
        session.add(addNewMovie)
        session.commit()
        flash('New Movie Item Successfully Created')
        return redirect(url_for('showGenres'))
    else:
        return render_template('newMovie.html', genres=genres)


# Edit a movie


@app.route('/genres/<int:genre_id>/movies/<int:movies_name_id>/edit', methods=['GET', 'POST'])
def editMovie(genre_id, movies_name_id):
    if 'username' not in login_session:
        return redirect('/login')
    editedMovie = session.query(Movies_name).filter_by(id=movies_name_id).one()
    genre = session.query(Movies_Genre).all()
    if login_session['user_id'] != editedMovie.user_id:
        return "<script>function myFunction() {alert('You are not authorized to edit movies to this genre. Please create your own genre in order to edit movies.');}</script><body onload='myFunction()'>"
    if request.method == 'POST':
        if request.form['name']:
            editedMovie.name = request.form['name']
        if request.form['description']:
            editedMovie.description = request.form['description']
        if request.form['price']:
            editedMovie.price = request.form['price']
        if request.form['year']:
            editedMovie.year = request.form['year']
        session.add(editedMovie)
        session.commit()
        flash('Movie Successfully Edited','success')
        return redirect(url_for('showGenres'))
    else:
        return render_template('editMovie.html',genre=genre,item=editedMovie)


# Delete a  movie item
@app.route('/genres/<int:genre_id>/movies/<int:movies_name_id>/delete', methods=['GET', 'POST'])
def deleteMovie(genre_id, movies_name_id):
    if 'username' not in login_session:
        return redirect('/login')
    genre = session.query(Movies_Genre).filter_by(id=genre_id).one()
    movieToDelete = session.query(Movies_name).filter_by(id=movies_name_id).one()
    if login_session['user_id'] != movieToDelete.user_id:
        return "<script>function myFunction() {alert('You are not authorized to delete movies to this genre. Please create your own genre in order to delete movies.');}</script><body onload='myFunction()'>"
    if request.method == 'POST':
        session.delete(movieToDelete)
        session.commit()
        flash('Movie Successfully Deleted','success')
        return redirect(url_for('showGenres'))
    else:
        return render_template('deleteMovie.html', item=movieToDelete)



# Disconnect based on provider
@app.route('/disconnect')
def disconnect():
    if 'provider' in login_session:
        if login_session['provider'] == 'google':
            gdisconnect()
            del login_session['gplus_id']
            del login_session['access_token']
        if login_session['provider'] == 'facebook':
            fbdisconnect()
            del login_session['facebook_id']
        del login_session['username']
        del login_session['email']
        del login_session['picture']
        del login_session['user_id']
        del login_session['provider']
        flash("You have successfully been logged out.")
        return redirect(url_for('showGenres'))
    else:
        flash("You were not logged in")
        return redirect(url_for('showGenres'))


if __name__ == '__main__':
    app.secret_key = 'super_secret_key'
    app.debug = False
    app.run(host='0.0.0.0', port=5000)
