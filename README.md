# Hostel Energy Advisor

A local tool that reads a hostel's half-hourly electricity and solar data and reports:

- how much the hostel could save each month by changing when things run,
- which usage patterns it has,
- how accurately usage can be predicted,
- whether a battery would pay for itself at the price you enter.

Everything runs on your own computer. Uploaded data is never sent anywhere.

## Project layout

```
AI Project/
├── app.py                          # web server and page logic (run this)
├── ui.html                         # the page you see in the browser
├── requirements.txt                # Python packages needed
├── README.md                       # this file
├── step1_prepare.py                # Step 1: clean data, build features, train/test split
├── step2_regression.py             # Step 2: demand forecast (ridge and random forest)
├── step3_pca_kmeans.py             # Step 3: PCA and K-means usage patterns
├── step4_advisor.py                # Step 4: move laundry and pumps to cheaper / solar hours
├── step5_savings_levers.py         # Step 5: habit changes (AC, pre-cooling, geyser, timing)
├── step6_battery_size_optimum.py   # Step 6: battery size and replacement analysis
│
├── Datasets/
│   ├── hostel_energy_dataset_3months.csv   # full 3-month dataset
│   ├── train.csv                           # training split (written by step 1)
│   ├── test.csv                            # test split (written by step 1)
│   ├── test1.csv                           # sample 1
│   ├── test2.csv                           # sample 2
│   └── test3.csv                           # sample 3
│
├── Regression/
│   └── test_predictions.csv        # step 2 output
├── Clustering/
│   ├── cluster_labels.csv          # step 3 output
│   └── clusters.png                # step 3 chart
├── Basic Advisor/
│   ├── advisor_schedule.csv        # step 4 output
│   └── savings.png                 # step 4 chart
├── Intermediate Advisor/
│   ├── savings_levers.csv          # step 5 output
│   ├── levers.png                  # step 5 chart
│   └── battery_sizing.csv          # battery sizing table
│
├── battery_size_optimum.csv        # step 6 output (summary by scenario)
└── battery_size_profit_curve.csv   # step 6 output (profit by battery size)
```

The folders and output files are created when the steps run. Your step files write them into these folders, and the app finds them there wherever they are.

Files you can delete: `hostel-energy-advisor.html` (an older version of the page, no longer used) and `.venv` is only needed for running the app.

## Setup (one time)

You need Python 3.10 or newer.

1. Open Terminal and go to the project folder:
   ```
   cd "/Users/yourname/AI Project"
   ```
2. Create a virtual environment and install the packages:
   ```
   python3 -m venv .venv
   .venv/bin/pip install -r requirements.txt
   ```

## Running the app

```
.venv/bin/python app.py
```

Your browser opens at `http://localhost:8000`. If it does not, open that address yourself.
Keep the Terminal window open while you use the app. Stop the app with Ctrl+C.

## Using the app

1. **Set the battery price.** Enter the cost per kWh of a battery in the "Battery cost per kWh" box (default ₹25,000). You can change it at any time before running a file.
2. **Choose your data.**
   - Drag a CSV file onto the box, or click the box to choose one, **or**
   - click **Sample 1**, **Sample 2** or **Sample 3** to try an example.
3. **Read the results.**
   - Leave "Walk me through the results step by step" ticked to see one section at a time, with an explanation on each page.
   - Untick it to see everything on one page.

### What your file needs

- One row every 30 minutes, for at least 3 weeks (3 months is best).
- A date and time column (for example `timestamp`).
- A total electricity used column (name contains "total").
- A solar electricity made column (name contains "solar").

Optional columns make the advice richer: price per kWh, laundry, water pumps, water heaters, and air conditioners. Missing optional columns are assumed, and the results page lists them.

## The steps, in order

When you run a file, the app copies the whole project into a temporary folder and runs steps 1 to 6 there, so your original files are never changed. It shows the progress of each step on screen.

| Step | File | What it does |
|---|---|---|
| 1 | step1_prepare.py | Cleans the data and creates the features. Splits the data by time: the earlier part for training, the last 30% for testing. |
| 2 | step2_regression.py | Predicts usage with ridge regression and a random forest. Compares them with "same as last week". |
| 3 | step3_pca_kmeans.py | Reduces the appliance columns with PCA and groups time slots with K-means. |
| 4 | step4_advisor.py | Moves laundry and pumps to solar hours and cheap tariff hours. |
| 5 | step5_savings_levers.py | Tests habit changes: AC setpoint, afternoon pre-cooling, geyser storage, timing. |
| 6 | step6_battery_size_optimum.py | Finds the battery size with the best profit, allowing for replacement when it wears out. |

## Assumptions to know about

- **Tariff:** if no price column is given, the app assumes ₹5.5 per kWh from 22:00 to 06:00, ₹7 from 06:00 to 18:00, and ₹9.5 from 18:00 to 22:00.
- **Battery:** 90% round-trip efficiency, a 10% minimum charge, and replacement after 12 years or 4,000 full cycles, whichever comes first. The bills and replacement years come from step 6; the profit column is recalculated for the price you enter.
- **Habit changes:** the savings percentages (for example 12% less AC energy for 2 °C warmer) are planning assumptions, not measurements.
- **Results** are estimates from the data provided. Get supplier quotes before buying equipment.

## Troubleshooting

**"Address already in use" / port 8000 is busy**
An earlier copy of the app is still running. Stop it:
```
lsof -ti :8000 | xargs kill
```
Or run on another port: `PORT=8001 .venv/bin/python app.py`, then open `http://localhost:8001`.

**"Could not find the sample file test1.csv"**
Put the file in the `Datasets` folder next to `app.py`. The sample buttons only appear when their files are present.

**A step fails with a FileNotFoundError**
Check that the step files are the ones this README describes, and that the step is writing its output to a folder in the project. The error message names the step and the missing file.

**The page shows old numbers**
Restart the app and hard-refresh the browser (Cmd+Shift+R on a Mac).

**"Your file is missing a date and time column" (or similar)**
Add the missing column to your CSV, using the names in "What your file needs".

## Limitations

- The bundled datasets are simulated. They follow realistic patterns, but they are not measured data from a real hostel.
- The samples cover 30 days, so their battery results are less reliable than the 3-month analysis.
- Weather is taken as recorded. A real deployment would need a weather forecast.
