from decimal import Decimal, InvalidOperation

import pandas as pd
from flask import Flask, render_template, request, jsonify
from datetime import datetime, timedelta

from Backend.MarketData.YahooAPI.market_data_source import get_market_data, get_current_price, \
    get_stock_info, get_asset_name  # Import your function here
from Backend.Database.DB_communication import (
    create_asset, read_assets, update_asset, delete_asset,
    create_category, read_categories, update_category, delete_category,
    create_transaction, read_transactions, update_transaction, delete_transaction,
    buy_stock, sell_stock
)


class CashAmount:
    USD = 0


app = Flask(
    __name__,
    template_folder='Frontend/Dashboard',  # Set template folder to Dashboard
    static_folder='Frontend/Dashboard'  # Set static folder to Dashboard
)
app.config.from_object(CashAmount)


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
    assets = read_assets()
    transactions = read_transactions()
    asset_prices = get_assets_market_price()
    return render_template('index.html', assets=assets, transactions=transactions, asset_prices=asset_prices)


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
def get_market_data_api(stock, start_date, end_date, interval):
    start_date_dt = datetime.strptime(start_date, '%Y-%m-%d')
    end_date_dt = datetime.strptime(end_date, '%Y-%m-%d')
    df = get_market_data(stock, start_date_dt, end_date_dt, interval)
    return df.to_json(orient='records')


@app.route("/api/get_time_series", methods=['GET'])
def get_asset_time_series_value():
    tickers = get_tickers_from_assets()
    time_series_dict = {}
    for ticker in tickers:
        time_now = datetime.now()
        df = pd.DataFrame(get_market_data(ticker, time_now - timedelta(days=1), time_now, '30m')["Close"])
        time_series_dict[ticker] = {
            'Date': df.index.tolist(),
            'Close': df['Close'].tolist()
        }
    return jsonify(time_series_dict)


@app.route("/api/get_current_price/<string:stock>")
def get_current_price_api(stock):
    try:
        price = get_current_price(stock)
        return jsonify({'price': price})
    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        return jsonify({'error': 'An unexpected error occurred.'}), 500


@app.route("/api/get_stock_info/<string:stock>")
def get_stock_info_api(stock):
    return get_stock_info(stock)


@app.route("/api/get_net_value")
def get_net_value():
    assets = read_assets()
    total_value = 0
    for asset in assets:
        stock_value = get_current_price(asset["symbol"])
        stock_quantity = asset["quantity"]
        total_value += stock_value * stock_quantity
    return total_value


@app.route("/api/add_funds/<int:deposit_amount>")
def add_funds(deposit_amount):
    CashAmount.USD += deposit_amount


@app.route("/api/get_funds")
def get_funds():
    return CashAmount.USD


@app.route("/api/get_unrealized_profit", methods=['GET'])
def get_unrealized_profit():
    assets = read_assets()
    profit = 0
    for asset in assets:
        if asset["category_name"] == 'Stock':
            profit += get_asset_unrealized_profit(asset)
    return jsonify(round(profit, 2)), 200


def get_asset_unrealized_profit(asset):
    purchase_price_total = float(asset["total_purchase_price"])
    total_current_asset_value = float(asset["quantity"]) * get_current_price(asset["symbol"])
    return total_current_asset_value - purchase_price_total


@app.route('/buy_stock', methods=['POST'])
def buy_stock_endpoint():
    data = request.get_json()
    input_symbol = data.get('symbol')

    try:
        long_name = get_asset_name(input_symbol)
    except KeyError:
        return jsonify({'error': f'Long name not found for symbol {input_symbol}'}), 400

    try:
        purchase_price = Decimal(str(get_current_price(input_symbol)))
        input_quantity = Decimal(data.get('quantity'))
    except (TypeError, ValueError, InvalidOperation) as e:
        return jsonify({'error': 'Invalid price or quantity provided'}), 400

    if not input_symbol or not long_name or not purchase_price or not input_quantity:
        return jsonify({'error': 'Missing required parameters'}), 400

    result, status_code = buy_stock(input_symbol, long_name, purchase_price, input_quantity)
    return jsonify(result), status_code


@app.route('/sell_stock', methods=['POST'])
def sell_stock_endpoint():
    data = request.get_json()

    input_symbol = data.get('symbol')

    try:
        selling_price = Decimal(str(get_current_price(input_symbol)))
        input_quantity = Decimal(data.get('quantity'))
    except (TypeError, ValueError, InvalidOperation) as e:
        return jsonify({'error': 'Invalid price or quantity provided'}), 400

    if not input_symbol or not selling_price or not input_quantity:
        return jsonify({'error': 'Missing required parameters'}), 400

    result, status_code = sell_stock(input_symbol, selling_price, input_quantity)
    return jsonify(result), status_code


@app.route('/api/get_transactions')
def get_transactions():
    return read_transactions()


def get_assets_market_price():
    ticker_names = get_tickers_from_assets()
    ticker_price_list = []
    for ticker in ticker_names:
        price = get_current_price(ticker)
        asset_name = get_asset_name(ticker)
        ticker_price_list.append({
            'asset_name': asset_name,
            'price': round(price, 2),
            'ticker_name': ticker
        })
    return ticker_price_list


def get_tickers_from_assets():
    assets = read_assets()
    ticker_names = set()
    for asset in assets:
        if asset["category_name"] == 'Stock':
            ticker_names.add(asset["symbol"])
    return ticker_names


@app.route("/api/get_long_name/<string:ticker>")
def get_long_name_api(ticker):
    result = {
        'name': get_asset_name(ticker)
    }
    return jsonify(result)


if __name__ == '__main__':
    app.run(debug=True)
