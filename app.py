from flask import Flask, render_template, request
from apscheduler.schedulers.background import BackgroundScheduler
from scanner import run_scanner, get_signal_history

app = Flask(__name__)
results = []

def update_data():
    global results
    results = run_scanner()

scheduler = BackgroundScheduler()
scheduler.add_job(update_data, 'interval', minutes=15)
scheduler.start()

@app.route("/")
def index():
    filter_buy = request.args.get('filter') == 'buy'
    # Filter results if requested
    filtered_results = [r for r in results if r['signal'] == 'BUY'] if filter_buy else results
    history = get_signal_history()
    return render_template("index.html", results=filtered_results, history=history, filter_buy=filter_buy)

if __name__ == "__main__":
    update_data()  # Initial fetch
    app.run(debug=True, port=5010)
