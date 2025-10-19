# 🧠 Steam Market Portfolio — Blade RUNNER Edition

## 📜 Project Overview
**Steam Market Portfolio** is a desktop application built with **Python + Tkinter** for managing a personal portfolio of Steam Market items (especially CS2/CS:GO).  
It allows you to track item prices in real time, calculate profit and loss, and export reports in CSV or HTML formats.

The interface is inspired by the **Blade Runner** aesthetic — glowing neon accents, violet–cyan palette, and subtle transparency.

---

## 🔒 Privacy & Security

- ❌ The application **does not connect to your Steam account**.  
- 🧾 All item data (names, quantities, purchase prices) are **entered manually** by the user.  
- 🌐 Current prices are fetched **directly from the official Steam Market** via the public `priceoverview` API — no login or authentication required.  
- 💽 All data and database files (`portfolio.db`) are stored **locally** on your device.  

> 💡 100% safe — the app does **not collect, store, or transmit** any personal or account-related information.

---

## ⚙️ Key Features

| Feature | Description |
|----------|-------------|
| 🔍 **Fetch Steam Data** | Retrieves current market prices by `market_hash_name` or Steam item link. |
| 💰 **Buy & Add to Stock** | Adds a new item purchase or updates an existing one, recalculating average cost. |
| 📊 **Table View** | Displays your portfolio with color-coded profit/loss indicators. |
| 📈 **Show Selected Item Chart** | (Planned) Displays price history using `matplotlib`. |
| 🔁 **Update All Steam Prices** | Updates all current prices via Steam API. |
| 📥 **Import from CSV** | Imports portfolio data from CSV (e.g., Excel). |
| 📤 **Export to CSV / HTML** | Exports portfolio data with a neon-styled HTML report. |
| 💼 **Profit Calculation** | Calculates total investment, current value, and profit. |

---

## 🧩 Technical Details

- **Language:** Python 3.10+
- **GUI:** `tkinter` + `ttk` (custom themed)
- **Database:** SQLite (`portfolio.db`)
- **HTTP Requests:** `requests`
- **Charts:** `matplotlib`
- **Data Handling:** `csv`, `pandas`, `numpy`
- **Theme:** Cyberpunk / Blade Runner (violet–cyan neon aesthetic)
- **Steam API:** `https://steamcommunity.com/market/priceoverview`

---

## 📂 Database Structure (`items` table)

| Field | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Unique ID |
| `market_name` | TEXT | Steam Market hash name |
| `display_name` | TEXT | Display name |
| `qty` | INTEGER | Quantity owned |
| `buy_price` | REAL | Average purchase price |
| `current_price` | REAL | Current Steam Market price |

---

## 🖥️ Interface

- Window size: **900×900 px**  
- Transparency: `alpha = 0.95`  
- Color palette:  
  - Background — `#0F1626`  
  - Neon Cyan — `#00FFFF`  
  - Neon Magenta — `#FF00FF`

**Profit visualization:**
- 💚 Positive — highlighted in neon blue  
- 🟣 Negative — shaded purple  

---

## 🧮 Profit Example

