from flask import Flask, render_template, request
import subprocess

app = Flask(__name__)

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        # Get the selected date from the form
        selected_date = request.form["calendar"]
        formatted_date = selected_date.replace("-", "")  # Format as YYYYMMDD

        # Call the satellite Python script and pass the date
        try:
            subprocess.run(
                ["python", "satellite_LST_correlation_QuHacks.py", formatted_date], 
                check=True
            )
            return render_template("index.html", success=True, selected_date=selected_date)
        except subprocess.CalledProcessError as e:
            return render_template("index.html", error=f"Error: {e}", selected_date=selected_date)
    return render_template("index.html")
