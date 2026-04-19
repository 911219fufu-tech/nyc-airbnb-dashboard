# NYC Airbnb Performance Dashboard

A polished interactive dashboard built with Plotly Dash to analyze Airbnb pricing, demand, neighborhood performance, and seasonal revenue trends across New York City.

## Features

- Responsive, card-based dashboard layout with a modern neutral visual system
- Coordinated filters for neighborhood, room type, price range, and monthly snapshot selection
- Interactive map where price is encoded by color and revenue is encoded by bubble size
- Cross-filtered scatterplot for spotting overpriced or underperforming listings
- Sorted neighborhood ranking view for comparing demand concentration
- Historical time series to reveal seasonal revenue trends
- Reset control and loading states for smoother exploration

## Project Structure

- `app.py`: Dash app with modular sections for data loading, layout, figures, and callbacks
- `assets/dashboard.css`: UI styling for the dashboard
- `listings_monthly.csv`: source dataset used by the app

## Local Run

1. Create and activate a virtual environment.

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies.

```bash
pip install -r requirements.txt
```

3. Start the Dash server.

```bash
python app.py
```

4. Open `http://127.0.0.1:8050` in your browser.

## Deployment

This app is ready for common Python web hosts such as Render, Railway, or Dash Enterprise.

### Procfile-style command

```bash
gunicorn app:server
```

### Environment

- Python 3.10+ recommended
- Optional `PORT` environment variable is supported automatically by `app.py`

## Notes

- The dashboard defaults to the latest well-populated month in the dataset instead of the absolute latest month, which avoids thin or incomplete snapshot views.
- The line chart keeps the full historical trend for the currently filtered market and highlights the selected snapshot month.
- Drag on the map to select listings and focus the rest of the dashboard on that subset.
