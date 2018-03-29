# Moviestore-Catalog
Udacity Full Stack Project- Movie Store app to add genres and movies available.  

# Project Overview
An application that provides a list of movies within a variety of genres as well as provide a user registration and authentication system. Registered users will have the ability to post, edit and delete their own genres and movies.

# Technologies and Languages used in this project
- Python
- HTML
- Bootstrap
- OAuth
- Facebook / Google Login
- Flask Framework
- Jinja2
- SQLAchemy

# Setup and how to Run
- Install Vagrant and VirtualBox.
- Clone the fullstack-nanodegree-vm repository.
- Launch the Vagrant VM (vagrant up) and vagrant ssh.
- Go into catalog folder(cd /vagrant/catalog).
- Copy the files from this repository to the catalog folder.
- Run database_setup.py in terminal to initialize database(python database_setup.py).
- Run the python file application.py (python application.py).
- Access and test the application by visiting http://localhost:5000 locally.

# Screenshots of the working application

<img src="pics/Homepage.png" width="800"/>

<img src="pics/genre.png" width="800">
![genre](https://github.com/vishwas-c/Moviestore-Catalog/blob/master/pics/Homepage.PNG)
<img src="pics/edit.png" width="800">

# Known Issues
- Facebook login not working on localhost as Facebook has made it mandatory for url origin to be https://.

# Future Improvements
- Hosting on heroku.
- Add CRUD functionality for image handling.
- Implement CSRF protection on your CRUD operations.

# Credits 
Referred to code provided by Udacity mentor Lorenzo Brown to build Restaurant Menu App.


