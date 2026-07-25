import os

from app import create_app


app = create_app()


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    # Enable threaded mode so multiple devices can POST concurrently from the LAN
    app.run(host="0.0.0.0", port=port, debug=os.getenv("FLASK_DEBUG") == "1", threaded=True)
