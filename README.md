# Hostel Energy Advisor

A tool that reads a hostel's half-hourly electricity and solar data and reports:

- how much the hostel could save each month by changing when things run,
- which usage patterns it has,
- how accurately usage can be predicted,
- whether a battery would pay for itself at the price you enter.

It runs entirely on your own computer. Uploaded data is never sent anywhere.

---

## 1. Get the project onto your device

Choose one of the two options below.

### Option A: download as a ZIP (no tools needed)

1. Open the project's repository page in your browser: `https://github.com/PrincePatel2007/Energy_Usage_Advisor`
2. Click the green **Code** button, then **Download ZIP**.
3. Open the downloaded ZIP. Your computer unzips it into a folder, usually called `AI-Project` or similar.
4. Move that folder somewhere easy to find, such as your Desktop or Documents.

### Option B: clone with Git (recommended if you may update later)

1. Check whether Git is installed. Open Terminal (Mac) or Command Prompt / PowerShell (Windows) and type:
   ```
   git --version
   ```
   If you see a version number, go to step 2. Otherwise install Git from https://git-scm.com/downloads and reopen the terminal.
2. Go to the folder where you want the project, then clone it:
   ```
   cd ~/Desktop
   git clone https://github.com/PrincePatel2007/Energy_Usage_Advisor "AI Project"
   cd "AI Project"
   ```
3. To get future updates later, run `git pull` inside the project folder.

### Check that you have all the files

After either option, the folder should contain at least:

```
app.py   ui.html   requirements.txt   README.md
step1_prepare.py ... step6_battery_size_optimum.py
Datasets/   (with hostel_energy_dataset_3months.csv, test1.csv, test2.csv, test3.csv)
```

If `Datasets/` or the sample files are missing, the sample buttons will not appear. Get the full folder again.

---

## 2. Install Python (one time)

You need Python 3.10 or newer.

- **Check first.** In the terminal, type `python3 --version` (Mac) or `python --version` (Windows). If it shows 3.10 or higher, skip this section.
- **Mac:** download the installer from https://www.python.org/downloads/ and run it, or, if you use Homebrew, run `brew install python`.
- **Windows:** download the installer from https://www.python.org/downloads/. On the first screen, tick **"Add python.exe to PATH"**, then click **Install Now**.

---

## 3. Open a terminal inside the project folder

- **Mac:** open the Terminal app, type `cd ` (with a space), drag the project folder onto the Terminal window, and press Enter.
- **Windows:** open the project folder in File Explorer, click the address bar, type `cmd` and press Enter.

Check that you are in the right place. This should list `app.py`:

```
ls            (Mac)
dir           (Windows)
```

---

## 4. Set up the environment (one time)

This installs the packages the app needs, in a private folder called `.venv` inside the project.

**Mac / Linux:**
```
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

**Windows:**
```
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

This takes a few minutes the first time. You only need to do it once. Do not upload the `.venv` folder to a repository; it is specific to your computer.

---

## 5. Run the app

**Mac / Linux:**
```
.venv/bin/python app.py
```

**Windows:**
```
.venv\Scripts\python app.py
```

You will see:

```
Hostel Energy Advisor running at http://localhost:8000  (press Ctrl+C to stop)
```

Your browser opens the page automatically. If it does not, open `http://localhost:8000` yourself.

**Keep the terminal window open** while you use the app. Closing it stops the app.

---

## 6. Use the app

1. **Set the battery price.** Enter the cost per kWh of a battery in the "Battery cost per kWh" box (default ₹25,000). You can change it at any time before running a file.
2. **Choose your data.** Either:
   - drag a CSV file onto the box, or click the box to choose one, **or**
   - click **Sample 1**, **Sample 2** or **Sample 3** to try an example.
3. **Wait a few seconds.** The progress list ticks off each of the six steps.
4. **Read the results.**
   - Leave "Walk me through the results step by step" ticked to see one section at a time, with an explanation on each page. Use **Next** and **Back**.
   - Untick it to see everything on one page.
   - Choose **Check another file** to start again.

### What your file needs

- One row every 30 minutes, for at least 3 weeks (3 months is best).
- A date and time column (for example `timestamp`).
- A total electricity used column (its name contains "total").
- A solar electricity made column (its name contains "solar").

Optional columns make the advice richer: price per kWh, laundry, water pumps, water heaters, and air conditioners. Missing optional columns are assumed, and the results page lists them.

---

## 7. Stop the app and run it again later

- **Stop:** press Ctrl+C in the terminal window.
- **Run again:** open the terminal in the project folder (step 3) and run the command from step 5. You do not need to repeat step 4.

---

## How the app works

When you run a file, the app copies the whole project into a temporary folder and runs steps 1 to 6 there, so your original files are never changed. Each step writes its results into the project's output folders. The app finds those files wherever they land.

| Step | File | What it does |
|---|---|---|
| 1 | step1_prepare.py | Cleans the data and creates the features. Splits the data by time: the earlier part for training, the last 30% for testing. |
| 2 | step2_regression.py | Predicts usage with ridge regression and a random forest. Compares them with "same as last week". |
| 3 | step3_pca_kmeans.py | Reduces the appliance columns with PCA and groups time slots with K-means. |
| 4 | step4_advisor.py | Moves laundry and pumps to solar hours and cheap tariff hours. |
| 5 | step5_savings_levers.py | Tests habit changes: AC setpoint, afternoon pre-cooling, geyser storage, timing. |
| 6 | step6_battery_size_optimum.py | Finds the battery size with the best profit, allowing for replacement when it wears out. |

---

## Project layout

```
AI Project/
├── app.py                          # web server and page logic (run this)
├── ui.html                         # the page you see in the browser
├── requirements.txt                # Python packages needed
├── README.md                       # this file
├── step1_prepare.py                # Step 1
├── step2_regression.py             # Step 2
├── step3_pca_kmeans.py             # Step 3
├── step4_advisor.py                # Step 4
├── step5_savings_levers.py         # Step 5
├── step6_battery_size_optimum.py   # Step 6
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

The output folders and files are created when the steps run.

**Safe to delete:** `hostel-energy-advisor.html` (an older version of the page, no longer used).

**Keep out of a repository:** `.venv/` (your local Python environment) and `__pycache__/` (Python's cache). Add these lines to a `.gitignore` file in the project folder:

```
.venv/
__pycache__/
```

---

## Troubleshooting

**"Address already in use" / port 8000 is busy**
An earlier copy of the app is still running. Stop it:
- Mac: `lsof -ti :8000 | xargs kill`
- Or close the terminal window that is running it and press Ctrl+C there.

Or run on another port: `PORT=8001 .venv/bin/python app.py` (Mac), then open `http://localhost:8001`.

**"command not found: python3" or "python is not recognised"**
Python is not installed or not on your PATH. Repeat step 2. On Windows, make sure "Add python.exe to PATH" was ticked.

**"No module named pandas" (or similar)**
The packages are not installed in `.venv`. Run the install command from step 4 again.

**"Could not find the sample file test1.csv"**
Put the file in the `Datasets` folder next to `app.py`. The sample buttons only appear when their files are present.

**A step fails with a FileNotFoundError**
Check that the step files match this README and that the folders are complete. The error message names the step and the missing file.

**The page shows old numbers**
Restart the app and hard-refresh the browser (Cmd+Shift+R on a Mac, Ctrl+F5 on Windows).

**"Your file is missing a date and time column" (or similar)**
Add the missing column to your CSV, using the names in "What your file needs".

---

## Assumptions

- **Tariff:** if no price column is given, the app assumes ₹5.5 per kWh from 22:00 to 06:00, ₹7 from 06:00 to 18:00, and ₹9.5 from 18:00 to 22:00.
- **Battery:** 90% round-trip efficiency, a 10% minimum charge, and replacement after 12 years or 4,000 full cycles, whichever comes first. The bills and replacement years come from step 6; the profit column is recalculated for the price you enter.
- **Habit changes:** the savings percentages (for example 12% less AC energy for 2 °C warmer) are planning assumptions, not measurements.
- **Results** are estimates from the data provided. Get supplier quotes before buying equipment.

## Limitations

- The bundled datasets are simulated. They follow realistic patterns, but they are not measured data from a real hostel.
- The samples cover 30 days, so their battery results are less reliable than the 3-month analysis.
- Weather is taken as recorded. A real deployment would need a weather forecast.
