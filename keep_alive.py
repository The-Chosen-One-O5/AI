    from flask import Flask
    from threading import Thread
    import os # Import os to potentially get port

    app = Flask('')

    @app.route('/')
    def home():
        return "I'm alive!"

    def run():
        # Render provides the PORT environment variable
        port = int(os.environ.get('PORT', 8080)) # Default if PORT isn't set
        app.run(host='0.0.0.0', port=port)

    def keep_alive():
        t = Thread(target=run)
        t.start()
        print("Keep-alive server started.")
    

