from flask import Flask

# needed for Flask to work
app = Flask(__name__)

@app.route("/")

def index():
    return "Hello,World!"

if __name__ == "__main__":
    app.run(debug=True)
