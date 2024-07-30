from flask import Flask, render_template, request, jsonify
from datetime import datetime
from Backend.MarketData.YahooAPI.market_data_source import get_market_data  # Import your function here

app = Flask(
    __name__,
    template_folder='Dashboard',  # Set template folder to Dashboard
    static_folder='Dashboard'  # Set static folder to Dashboard
)


def parse_request(data):
    """
    Helper function to parse the request data and return the parameters for get_market_data.
    """
    name = data.get('name', 'AAPL')  # Default to 'AAPL' if not provided
    start = datetime.strptime(data.get('start', '2022-01-01'), '%Y-%m-%d')
    end = datetime.strptime(data.get('end', '2022-12-31'), '%Y-%m-%d')
    interval = data.get('interval', '1d')
    return name, start, end, interval


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/run_python_code', methods=['POST'])
def run_python_code():
    try:
        # Extract parameters from request
        data = request.json
        name, start, end, interval = parse_request(data)

        # Run the Python function
        result = get_market_data(name, start, end, interval)
        # Convert result to JSON serializable format
        result_json = result.to_json(orient='split')
        return jsonify(result=result_json)
    except Exception as e:
        return jsonify(error=str(e)), 500


@app.route("/api/get_market_data/<string:stock>/<string:start_date>/<string:end_date>/<string:interval>",
           methods=['GET'])
def get_market_data_solution(stock, start_date, end_date, interval):
    start_date_dt = datetime.strptime(start_date, '%Y-%m-%d')
    end_date_dt = datetime.strptime(end_date, '%Y-%m-%d')
    df = get_market_data(stock, start_date_dt, end_date_dt, interval)
    return df.to_json(orient='records')


if __name__ == '__main__':
    app.run(debug=True)