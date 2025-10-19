import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sqlite3
import requests
import re
import csv
import time
import urllib.parse
import os 
from datetime import datetime
import pandas as pd
import numpy as np

# --- IMPORTS FOR CHART ---
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
# ---------------------------

# --- Cyberpunk Color Palette (Purple-Cyan Neon) ---
COLOR_BG_DARK = "#0F1626"       
COLOR_PRIMARY_ACCENT = "#00FFFF" # Cyan Neon
COLOR_SECONDARY_ACCENT = "#FF00FF" # Magenta Neon
COLOR_TEXT_LIGHT = "#E0E0E0"    
COLOR_TEXT_DIM = "#808080"      
COLOR_INPUT_BG = "#2C3E50"      
COLOR_BUTTON_NORMAL = "#1F2F4A"
COLOR_BUTTON_HOVER = "#00FFFF"  
COLOR_PROFIT_BAD = "#FF3333"    
COLOR_BORDER = "#8A2BE2"        

# --- TABLE COLORS (Blue-Cyan) ---
COLOR_TABLE_BG = "#053B50"      
COLOR_TABLE_TEXT = "#64CCC5"    
COLOR_TABLE_HEADING_BG = "#141E46"
COLOR_TABLE_SELECT_BG = "#64CCC5"
COLOR_TABLE_SELECT_TEXT = "#141E46"

# --- PROFIT COLORS ---
COLOR_PROFIT_GOOD = "#00FFFF" 
COLOR_TAG_PROFIT_BG = "#001C1C"
# -------------------------------------------

DB = "portfolio.db"
STEAM_APP = 730 # CS2 / CSGO app id
# Safe delay to prevent Steam blocking
STEAM_API_DELAY = 3.0 

# --------------- DB -----------------
def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        market_name TEXT UNIQUE,
        display_name TEXT,
        qty INTEGER,
        buy_price REAL,
        current_price REAL
    )
    """)
    conn.commit()
    conn.close()

def add_or_update_item(market_name, display_name, new_qty, new_buy_price, current_price): 
    """
    Adds a new item or updates an existing one, ADDING the new quantity 
    and CALCULATING the new average buy price.
    """
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    
    # 1. Check for existence and get old data
    c.execute("SELECT qty, buy_price FROM items WHERE market_name=?", (market_name,))
    r = c.fetchone()
    
    if r:
        # Item exists - Calculate new average price and total quantity
        old_qty, old_buy_price = r
        
        # Ensure values are float/int for calculation (DB stores them as such, but good practice)
        old_qty = old_qty or 0
        old_buy_price = old_buy_price or 0.0
        
        # Total cost of old items
        old_total_cost = old_qty * old_buy_price
        
        # Total cost of new items (the ones just bought)
        new_total_cost = new_qty * new_buy_price
        
        # Calculate new totals
        total_qty = old_qty + new_qty
        total_cost = old_total_cost + new_total_cost
        
        # Calculate new average buy price
        if total_qty > 0:
            avg_buy_price = round(total_cost / total_qty, 6)
        else:
            # Should not happen if new_qty > 0, but safety first
            avg_buy_price = 0.0 

        # Update
        c.execute("""
            UPDATE items 
            SET display_name=?, qty=?, buy_price=?, current_price=? 
            WHERE market_name=?
        """, (display_name, total_qty, avg_buy_price, current_price, market_name))
        
        message = f"Item updated! Total QTY: {total_qty}, Avg Buy Price: {avg_buy_price:.2f}"
    else:
        # Item does not exist - Insert
        c.execute("""
            INSERT INTO items (market_name, display_name, qty, buy_price, current_price)
            VALUES (?, ?, ?, ?, ?)
        """, (market_name, display_name, new_qty, new_buy_price, current_price))
        
        message = "New item added to portfolio."
        
    conn.commit()
    conn.close()
    return message

def get_items():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT id, market_name, display_name, qty, buy_price, current_price FROM items")
    rows = c.fetchall()
    conn.close()
    return rows

def get_item_by_id(item_id):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT market_name, display_name, qty, buy_price, current_price FROM items WHERE id=?", (item_id,))
    row = c.fetchone()
    conn.close()
    return row # (market_name, display_name, qty, buy_price, current_price)

def delete_item(item_id):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("DELETE FROM items WHERE id=?", (item_id,))
    conn.commit()
    conn.close()

def import_items_from_csv(file_path):
    """
    Imports items from a CSV file. 
    Expects CSV with columns: market_name, display_name, qty, buy_price, current_price
    NOTE: CSV Import logic is simplified; it OVERWRITES qty and buy_price 
    if the item exists, based on the CSV data.
    """
    imported_count = 0
    updated_count = 0
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    try:
        with open(file_path, 'r', newline='', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader) # Skip header

            # Indices corresponding to export order
            COL_MARKET_NAME = 0
            COL_DISPLAY_NAME = 1
            COL_QTY = 2
            COL_BUY_PRICE = 3
            COL_CURRENT_PRICE = 4
            
            for i, row in enumerate(reader):
                if len(row) < 5:
                    log_message(f"Skipping row {i+2}: not enough columns", "WARNING")
                    continue
                
                # Parsing and cleaning data
                market_name = row[COL_MARKET_NAME].strip()
                display_name = row[COL_DISPLAY_NAME].strip()
                
                try:
                    qty = int(row[COL_QTY].strip())
                    buy_price = parse_price_str(row[COL_BUY_PRICE])
                    current_price = parse_price_str(row[COL_CURRENT_PRICE])
                except ValueError as e:
                    log_message(f"Skipping row {i+2} ({market_name}): invalid number format - {e}", "ERROR")
                    continue
                
                if not market_name:
                    log_message(f"Skipping row {i+2}: empty market_name", "WARNING")
                    continue

                # Check for existence and update/insert
                c.execute("SELECT id FROM items WHERE market_name=?", (market_name,))
                if c.fetchone():
                    # Update (Overwrite, as CSV typically contains the desired final state)
                    c.execute("""
                        UPDATE items SET display_name=?, qty=?, buy_price=?, current_price=? WHERE market_name=?
                    """, (display_name, qty, buy_price, current_price, market_name))
                    updated_count += 1
                else:
                    # Insert
                    c.execute("""
                        INSERT INTO items (market_name, display_name, qty, buy_price, current_price)
                        VALUES (?, ?, ?, ?, ?)
                    """, (market_name, display_name, qty, buy_price, current_price))
                    imported_count += 1

        conn.commit()
        return imported_count, updated_count
        
    except FileNotFoundError:
        messagebox.showerror("Import Error", "File not found.")
        return 0, 0
    except Exception as e:
        messagebox.showerror("Import Error", f"An error occurred while reading the file: {e}")
        return 0, 0
    finally:
        conn.close()


# --------------- Helpers (Steam only) ---------------

HEADERS = {"User-Agent": "Mozilla/50.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}

def log_message(message, level="INFO"):
    """Logs messages with a timestamp."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {message}")

def parse_price_str(price_str):
    if not price_str:
        return 0.0
    s = price_str
    s = re.sub(r'[^\d\.,]', '', s) 
    if s.count(',') > 0 and s.count('.') > 0:
        s = s.replace(',', '')
    elif s.count(',') > 0 and s.count('.') == 0:
        s = s.replace(',', '.')
    
    try:
        # If the string contains only a number
        return round(float(s), 6) 
    except:
        return 0.0

def get_steam_price_and_name(market_hash_name):
    """Fetches price and name from Steam API."""
    price = 0.0
    display_name = market_hash_name 
    
    url_price = "https://steamcommunity.com/market/priceoverview/"
    params = {
        "appid": STEAM_APP,
        "currency": 1, # 1 = USD
        "market_hash_name": market_hash_name
    }
    
    log_message(f"START PRICE REQUEST: {market_hash_name}")

    try:
        r = requests.get(url_price, params=params, headers=HEADERS, timeout=15)
        
        if r.status_code == 200:
            data = r.json()
            if data.get('success'): 
                price_str = data.get("lowest_price") or data.get("median_price") or None
                price = parse_price_str(price_str) if price_str else 0.0
            
                display_name = market_hash_name
                if ' | ' in market_hash_name:
                     d = market_hash_name.split(' | ')[-1]
                     display_name = re.sub(r'\s*\([^)]+\)$', '', d).strip() 
                     
        elif r.status_code == 429:
             log_message(f"RATE LIMIT EXCEEDED (429) for {market_hash_name}. Increase STEAM_API_DELAY!", "ERROR")
        else:
             log_message(f"HTTP Error {r.status_code} for {market_hash_name}", "ERROR")

    except requests.exceptions.RequestException as e:
        log_message(f"Price request FAILED for {market_hash_name}: {e}", "ERROR")
    except Exception as e:
        log_message(f"General error in price request for {market_hash_name}: {e}", "CRITICAL")
          
    # Return price and name
    return price, display_name


# -----------------------------------------------------------------


# ---------------- GUI ----------------
init_db()
root = tk.Tk()
root.title("Steam Market Portfolio - Cyberpunk Edition")
# Set fixed window size 900x900
root.geometry("900x900") 
root.resizable(False, False) # Disable resizing
root.configure(bg=COLOR_BG_DARK)

# === ADD WINDOW OPACITY ===
try:
    # Set 95% opacity (0.95). Should work on Windows/macOS.
    root.attributes('-alpha', 0.95) 
except tk.TclError:
    pass
# =============================================

# --- ttk Styling ---
style = ttk.Style(root)
style.theme_use("clam")

style.configure('.', background=COLOR_BG_DARK, foreground=COLOR_TEXT_LIGHT, font=('Consolas', 10))
style.configure('TFrame', background=COLOR_BG_DARK)

# General TLabel style
style.configure('TLabel', background=COLOR_BG_DARK, foreground=COLOR_TEXT_LIGHT, font=('Consolas', 10))

# Accent TLabel style - cyan, larger (11) and bold
style.configure('Accent.TLabel', 
                 background=COLOR_BG_DARK, 
                 foreground=COLOR_PRIMARY_ACCENT, 
                 font=('Consolas', 11, 'bold')) 

# STYLE FOR CHART BUTTON
style.configure('Graph.TButton', 
                 background=COLOR_BUTTON_NORMAL, 
                 foreground=COLOR_PRIMARY_ACCENT,
                 font=('Consolas', 10, 'bold'),
                 relief='flat',
                 bordercolor=COLOR_BORDER,
                 borderwidth=1,
                 padding=[10, 5])
style.map('Graph.TButton',
           background=[('active', COLOR_BUTTON_HOVER)],
           foreground=[('active', COLOR_BG_DARK)])


style.configure('C.TButton', 
                 background=COLOR_BUTTON_NORMAL, 
                 foreground=COLOR_SECONDARY_ACCENT,
                 font=('Consolas', 10, 'bold'),
                 relief='flat',
                 bordercolor=COLOR_BORDER,
                 borderwidth=1,
                 padding=[10, 5])
style.map('C.TButton',
           background=[('active', COLOR_BUTTON_HOVER)],
           foreground=[('active', COLOR_BG_DARK)])
style.configure('C.TEntry',
                 fieldbackground=COLOR_INPUT_BG,
                 foreground=COLOR_TEXT_LIGHT,
                 insertcolor=COLOR_PRIMARY_ACCENT,
                 bordercolor=COLOR_BORDER,
                 borderwidth=1,
                 relief='flat')
style.configure('Treeview',
                 background=COLOR_TABLE_BG,
                 foreground=COLOR_TABLE_TEXT,
                 fieldbackground=COLOR_TABLE_BG,
                 rowheight=30,
                 borderwidth=0,
                 relief='flat',
                 font=('Consolas', 10))
style.map('Treeview', 
           background=[('selected', COLOR_TABLE_SELECT_BG)],
           foreground=[('selected', COLOR_TABLE_SELECT_TEXT)])
style.configure('Treeview.Heading',
                 background=COLOR_TABLE_HEADING_BG,
                 foreground=COLOR_PRIMARY_ACCENT,
                 font=('Consolas', 10, 'bold'),
                 relief='flat')
style.layout('Treeview.Heading', [('Treeview.treeheading.padding', {'sticky': 'nswe'}),
                                   ('Treeview.treeheading.text', {'sticky': 'nswe'})])
style.configure('Treeview', bordercolor=COLOR_BORDER, borderwidth=1)
# ---------------------------------------------------

# --- WIDTH CONSTANTS ---
ENTRY_MARKET_WIDTH = 40
ENTRY_DATA_WIDTH = 20
BUTTON_WIDTH = 18
# -------------------------

# =================================================================
# MAIN INPUT AND CONTROL FRAME
main_top_frame = ttk.Frame(root, style='TFrame', padding=(10, 10, 10, 10))
main_top_frame.pack(padx=8, pady=6, fill='x')

frm = ttk.Frame(main_top_frame, style='TFrame')
frm.pack(fill='x')

# Column configuration for even element distribution
frm.grid_columnconfigure(0, weight=0) # Label
frm.grid_columnconfigure(1, weight=1) # Entry field (takes main space)
frm.grid_columnconfigure(2, weight=0) # Button

# 1st row (Market Hash Name and Fetch)
ttk.Label(frm, text="Market_hash_name or URL:", style='Accent.TLabel').grid(row=0, column=0, sticky='w', pady=2)
entry_market = ttk.Entry(frm, width=ENTRY_MARKET_WIDTH, style='C.TEntry')
entry_market.grid(row=0, column=1, padx=6, pady=2, sticky='ew')

btn_fetch = ttk.Button(frm, text="Fetch Steam Data", width=22, style='C.TButton')
btn_fetch.grid(row=0, column=2, padx=6, pady=2, sticky='e') 

# 2nd row (Buy Price and Add/Update)
ttk.Label(frm, text="Buy Price (per unit):", style='Accent.TLabel').grid(row=1, column=0, sticky='w', pady=2)
entry_buy = ttk.Entry(frm, width=ENTRY_DATA_WIDTH, style='C.TEntry')
entry_buy.grid(row=1, column=1, sticky='w', pady=2, padx=6) 

# Button text changed to reflect the new cumulative logic
btn_add = ttk.Button(frm, text="Buy & Add to Stock", width=BUTTON_WIDTH, style='C.TButton') 
btn_add.grid(row=1, column=2, padx=6, pady=2, sticky='e') 

# 3rd row (Quantity and Delete Selected)
ttk.Label(frm, text="Quantity (to buy/sell):", style='Accent.TLabel').grid(row=2, column=0, sticky='w', pady=2)
entry_qty = ttk.Entry(frm, width=ENTRY_DATA_WIDTH, style='C.TEntry')
entry_qty.grid(row=2, column=1, sticky='w', pady=2, padx=6)

# Delete Button
btn_delete = ttk.Button(frm, text="Delete Selected", width=BUTTON_WIDTH, style='C.TButton')
btn_delete.grid(row=2, column=2, padx=6, pady=2, sticky='e')

# 4th row (Chart Button)
frm_chart_button = ttk.Frame(main_top_frame, style='TFrame', padding=(0, 10, 0, 0))
frm_chart_button.pack(fill='x')
frm_chart_button.grid_columnconfigure(0, weight=1)

# BUTTON FOR SELECTED ITEM CHART
btn_show_chart_selected = ttk.Button(frm_chart_button, 
                                     text="SHOW SELECTED ITEM CHART 📊", 
                                     width=30, 
                                     style='Graph.TButton') 
btn_show_chart_selected.grid(row=0, column=0, padx=6, pady=2, sticky='ew')
# =================================================================


# TABLE
cols = ("ID", "Name", "Qty", "BuyPrice", "SteamPrice", "TotalBuy", "TotalSteam", "ProfitSteam")
tree = ttk.Treeview(root, columns=cols, show='headings', height=15, style='Treeview') 

for c in cols:
    tree.heading(c, text=c)
    if c == "Name":
        tree.column(c, anchor='center', width=250)
    elif c in ("BuyPrice", "SteamPrice"):
        tree.column(c, anchor='center', width=100)
    elif c in ("TotalBuy", "TotalSteam", "ProfitSteam"):
        tree.column(c, anchor='center', width=120)
    else:
        tree.column(c, anchor='center', width=50) 
        
tree.pack(fill='both', expand=True, padx=8, pady=(10,8))

tree.tag_configure('profit', background=COLOR_TAG_PROFIT_BG, foreground=COLOR_PROFIT_GOOD)
tree.tag_configure('loss', background='#201212', foreground=COLOR_PROFIT_BAD)

# BOTTOM PANEL (Controls)
bottom = ttk.Frame(root, style='TFrame', padding=(10,5,10,5))
bottom.pack(fill='x', padx=8, pady=6)

btn_update = ttk.Button(bottom, text="Update All Steam Prices", width=25, style='C.TButton')
btn_import = ttk.Button(bottom, text="Import from CSV", width=18, style='C.TButton') 
btn_export_csv = ttk.Button(bottom, text="Export to CSV", width=18, style='C.TButton') 
btn_export_html = ttk.Button(bottom, text="Export to HTML", width=18, style='C.TButton') 
btn_author = ttk.Button(bottom, text="Author", width=10, style='C.TButton') 

btn_update.pack(side='left', padx=6)
btn_import.pack(side='left', padx=6) 
btn_export_csv.pack(side='left', padx=6) 
btn_export_html.pack(side='left', padx=6) 
# Author button packed last on the right
btn_author.pack(side='right', padx=6) 

# TOTALS PANEL
totals_frame = ttk.Frame(root, style='TFrame', padding=(10,10,10,10), relief='solid', borderwidth=1)
totals_frame.pack(fill='x', padx=8, pady=6)

lbl_total_buy = ttk.Label(totals_frame, text="TOTAL COST: $0.00", font=('Consolas', 11, 'bold'), foreground=COLOR_SECONDARY_ACCENT)
lbl_total_buy.pack(side='left', padx=10, fill='x', expand=True)

lbl_total_now_steam = ttk.Label(totals_frame, text="CURRENT STEAM VALUE: $0.00", font=('Consolas', 11, 'bold'), foreground=COLOR_PRIMARY_ACCENT)
lbl_total_now_steam.pack(side='left', padx=10, fill='x', expand=True)

lbl_total_profit_steam = ttk.Label(totals_frame, text="STEAM PROFIT: $0.00", font=('Consolas', 11, 'bold'), foreground=COLOR_TEXT_LIGHT)
lbl_total_profit_steam.pack(side='right', padx=10, fill='x', expand=True)


# states
fetched_market_name = None
fetched_steam_price = 0.0
fetched_display_name = "" 


# ------------- GUI FUNCTIONS ---------------
def refresh_table():
    for r in tree.get_children():
        tree.delete(r)

    rows = get_items() 
    total_now_steam = 0.0
    total_buy = 0.0
    
    for it in rows:
        _id, market_name, display_name, qty, buy_price, current_price = it 
        
        qty = qty or 0
        buy_price = buy_price or 0.0
        current_price = current_price or 0.0 
        
        total_now_steam_pos = current_price * qty
        total_buy_pos = buy_price * qty
        
        profit_steam = total_now_steam_pos - total_buy_pos
        
        total_now_steam += total_now_steam_pos
        total_buy += total_buy_pos
        
        vals = (
            _id, 
            market_name,  # ИСПОЛЬЗУЕМ ПОЛНЫЙ market_name
            qty, 
            f"{buy_price:.2f}", 
            f"{current_price:.2f}", 
            f"{total_buy_pos:.2f}", 
            f"{total_now_steam_pos:.2f}", 
            f"{profit_steam:+.2f}"
        )
        
        tag = 'profit' if profit_steam > 0 else 'loss' if profit_steam < 0 else ''
        
        item_id_str = f'item_{_id}'
        tree.insert("", tk.END, iid=item_id_str, values=vals, tags=(tag,))
        

    # footer
    total_profit_steam = total_now_steam - total_buy
    footer_vals = ("", "Totals:", "", "", "", f"{total_buy:.2f}", f"{total_now_steam:.2f}", f"{total_profit_steam:+.2f}")
    tree.insert("", tk.END, values=footer_vals, tags=('totals_row',))
    style.configure('Treeview', rowheight=30)
    tree.tag_configure('totals_row', background=COLOR_TABLE_HEADING_BG, foreground=COLOR_PRIMARY_ACCENT, font=('Consolas', 10, 'bold'))

    # UPDATE TOTALS LABELS
    lbl_total_buy.config(text=f"TOTAL COST: ${total_buy:.2f}")
    lbl_total_now_steam.config(text=f"CURRENT STEAM VALUE: ${total_now_steam:.2f}")
    
    if total_profit_steam >= 0:
        lbl_total_profit_steam.config(text=f"STEAM PROFIT: ${total_profit_steam:+.2f}", foreground=COLOR_PRIMARY_ACCENT)
    else:
        lbl_total_profit_steam.config(text=f"STEAM PROFIT: ${total_profit_steam:+.2f}", foreground=COLOR_PROFIT_BAD)


def on_fetch():
    global fetched_market_name, fetched_steam_price, fetched_display_name
    text = entry_market.get().strip()
    if not text:
        messagebox.showwarning("Error", "Enter market_hash_name or part of the URL")
        return
    
    m = re.search(r'/listings/\d+/(.+)$', text)
    if m:
        market = urllib.parse.unquote(m.group(1))
    else:
        market = text
        
    price, display = get_steam_price_and_name(market)
    
    fetched_market_name = market
    fetched_steam_price = price
    fetched_display_name = display
    
    log_message(f"Fetched price: {price:.2f} USD, Name: {display}")
    
    # Автоматически заполняем поле цены текущей ценой Steam для удобства
    entry_buy.delete(0, tk.END)
    entry_buy.insert(0, f"{price:.2f}") 
    
    time.sleep(STEAM_API_DELAY) 
    
    if price > 0.0:
        messagebox.showinfo("Done", f"Fetched: {display}\nSteam Price: {price:.2f} USD")
    else:
        messagebox.showwarning("Warning", f"Could not fetch Steam price for {display}. Check market_hash_name.")

def on_add():
    global fetched_market_name, fetched_steam_price, fetched_display_name
    if not fetched_market_name:
        messagebox.showwarning("Error", "First click \"Fetch Steam Data\"")
        return
        
    qtxt = entry_qty.get().strip()
    btxt = entry_buy.get().strip()
    
    if not qtxt or not btxt:
        messagebox.showwarning("Error", "Enter quantity and buy price")
        return
        
    try:
        qty = int(qtxt)
    except ValueError:
        messagebox.showwarning("Error", "Quantity must be an integer")
        return
    
    if qty <= 0:
        messagebox.showwarning("Error", "Quantity must be positive when adding.")
        return
        
    buy_price = parse_price_str(btxt)
    
    # Теперь add_or_update_item сам обрабатывает логику плюсования
    message = add_or_update_item(
        fetched_market_name, 
        fetched_display_name or fetched_market_name,
        qty, 
        buy_price, 
        fetched_steam_price
    )
    refresh_table()
    messagebox.showinfo("Operation Complete", message)

def on_update_all():
    
    original_btn_text = btn_update.cget("text")
    btn_update.config(state=tk.DISABLED, text="Updating... ⏳") 
    root.update()
    
    rows = get_items()
    if not rows:
        messagebox.showinfo("Update", "No items in the database")
        btn_update.config(state=tk.NORMAL, text=original_btn_text)
        return
    
    updated_count = 0
    total_items = len(rows)
    log_message(f"STARTING BATCH UPDATE for {total_items} items. Delay per item: {STEAM_API_DELAY}s")
    
    for i, it in enumerate(rows):
        _id, market_name, _, qty, buy_price, current_price = it 
        
        root.title(f"Steam Market Portfolio - Updating: {i+1}/{total_items} ({market_name})")
        
        if i > 0: 
            time.sleep(STEAM_API_DELAY) 
        
        price, display = get_steam_price_and_name(market_name)
        
        conn = sqlite3.connect(DB)
        c = conn.cursor()
        # Только обновляем текущую цену и display_name, остальные данные не трогаем
        c.execute("UPDATE items SET current_price=?, display_name=? WHERE id=?", (price, display, _id))
        conn.commit()
        conn.close()
        
        if price > 0.0:
              updated_count += 1
              
        refresh_table()
        root.update_idletasks()

    log_message("BATCH UPDATE FINISHED")
    
    root.title("Steam Market Portfolio - Cyberpunk Edition")
    btn_update.config(state=tk.NORMAL, text=original_btn_text)
    refresh_table()
    messagebox.showinfo("Update", f"Steam prices for all items updated. Successfully updated prices: {updated_count} out of {total_items}.")

def on_export_csv():
    """Export to CSV."""
    path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")], title="Save portfolio as CSV")
    if not path:
        return
    rows = get_items()
    with open(path, "w", newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        # Header, corresponding to the import order
        w.writerow(["market_name", "display_name", "qty", "buy_price", "current_price (Steam)"]) 
        for r in rows:
            _, market_name, display_name, qty, buy_price, current_price = r 
            w.writerow([market_name, display_name, qty, buy_price, current_price])
    messagebox.showinfo("Export", f"Exported {len(rows)} rows to {path}")

def on_export_html():
    """Export item list to an HTML file."""
    path = filedialog.asksaveasfilename(
        defaultextension=".html", 
        filetypes=[("HTML files", "*.html")],
        title="Save portfolio as HTML"
    )
    if not path:
        return

    rows = get_items() 
    if not rows:
        messagebox.showinfo("HTML Export", "Portfolio is empty. Nothing to export.")
        return
        
    # CSS for cyberpunk style
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Steam Market Portfolio Report</title>
        <style>
            body {{
                font-family: 'Consolas', monospace;
                background-color: {COLOR_BG_DARK};
                color: {COLOR_TEXT_LIGHT};
                padding: 20px;
            }}
            .header {{
                color: {COLOR_PRIMARY_ACCENT};
                text-align: center;
                border-bottom: 2px solid {COLOR_SECONDARY_ACCENT};
                padding-bottom: 10px;
                margin-bottom: 20px;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin-top: 20px;
                border: 1px solid {COLOR_BORDER};
            }}
            th, td {{
                padding: 12px 15px;
                text-align: center;
                border: 1px solid {COLOR_INPUT_BG};
            }}
            th {{
                background-color: {COLOR_TABLE_HEADING_BG};
                color: {COLOR_PRIMARY_ACCENT};
                font-size: 11px;
            }}
            tr:nth-child(even) {{
                background-color: {COLOR_TABLE_BG};
            }}
            tr:nth-child(odd) {{
                background-color: #1A2238; /* Slightly lighter dark */
            }}
            .profit-good {{ color: {COLOR_PROFIT_GOOD}; font-weight: bold; }}
            .profit-bad {{ color: {COLOR_PROFIT_BAD}; font-weight: bold; }}
            .total-row td {{
                background-color: {COLOR_TABLE_HEADING_BG} !important;
                color: {COLOR_SECONDARY_ACCENT};
                font-weight: bold;
                font-size: 12px;
            }}
        </style>
    </head>
    <body>
        <h1 class="header">Steam Market Portfolio Report</h1>
        <p style="color: {COLOR_TEXT_DIM};">Date Created: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
        <table>
            <thead>
                <tr>
                    <th>ID</th>
                    <th>Name</th>
                    <th>Qty</th>
                    <th>Buy Price ($)</th>
                    <th>Current Steam Price ($)</th>
                    <th>Total Cost ($)</th>
                    <th>Total Steam Value ($)</th>
                    <th>Profit ($)</th>
                </tr>
            </thead>
            <tbody>
    """
    
    total_buy = 0.0
    total_now_steam = 0.0
    
    for item in rows:
        _id, market_name, display_name, qty, buy_price, current_price = item
        
        qty = qty or 0
        buy_price = buy_price or 0.0
        current_price = current_price or 0.0 
        
        total_now_steam_pos = current_price * qty
        total_buy_pos = buy_price * qty
        profit_steam = total_now_steam_pos - total_buy_pos
        
        total_buy += total_buy_pos
        total_now_steam += total_now_steam_pos
        
        profit_class = "profit-good" if profit_steam >= 0 else "profit-bad"
        
        html_content += f"""
                <tr>
                    <td>{_id}</td>
                    <td style="text-align: left;">{market_name}</td> 
                    <td>{qty}</td>
                    <td>{buy_price:.2f}</td>
                    <td>{current_price:.2f}</td>
                    <td>{total_buy_pos:.2f}</td>
                    <td>{total_now_steam_pos:.2f}</td>
                    <td class="{profit_class}">{profit_steam:+.2f}</td>
                </tr>
        """
        
    total_profit = total_now_steam - total_buy

    html_content += f"""
                <tr class="total-row">
                    <td colspan="5" style="text-align: right;">TOTAL:</td>
                    <td>{total_buy:.2f}</td>
                    <td>{total_now_steam:.2f}</td>
                    <td class="{'profit-good' if total_profit >= 0 else 'profit-bad'}">{total_profit:+.2f}</td>
                </tr>
            </tbody>
        </table>
    </body>
    </html>
    """
    
    # Save the file
    try:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(html_content)
            
        messagebox.showinfo("HTML Export", f"Portfolio successfully exported to HTML:\n{path}")
        
    except Exception as e:
        messagebox.showerror("HTML Save Error", f"Could not save file: {e}")

def show_selected_item_chart():
    """
    Plots a comparison chart of the buy price and current Steam price 
    for the item selected in the table.
    """
    sel = tree.selection()
    if not sel:
        messagebox.showwarning("Error", "Select an item in the table to display the chart")
        return
        
    vals = tree.item(sel[0])['values']
    try:
        item_id = int(vals[0])
    except:
        messagebox.showwarning("Error", "Invalid item ID.")
        return

    # Get data from DB
    item_data = get_item_by_id(item_id)
    if not item_data:
        messagebox.showerror("Error", "Data for the selected item not found.")
        return
        
    market_name, display_name, qty, buy_price, current_price = item_data
    
    # Prepare data for chart
    labels = ['Buy Price', 'Current Steam Price']
    values = [buy_price, current_price]
    # Используем market_name для названия графика
    item_name = market_name 
    
    # Colors: Buy (magenta), Current (cyan)
    colors = [COLOR_SECONDARY_ACCENT, COLOR_PRIMARY_ACCENT]
    
    # Matplotlib setup for cyberpunk style
    plt.style.use('dark_background')
    # Use a size that fits the target window
    fig, ax = plt.subplots(figsize=(6, 5)) 
    
    # Chart background
    fig.patch.set_facecolor(COLOR_BG_DARK)
    ax.set_facecolor('#1A2238') 
    
    # Plot bar chart
    bars = ax.bar(labels, values, color=colors, alpha=0.8)

    # Axis and title settings
    ax.set_ylabel('Price ($)', color=COLOR_PRIMARY_ACCENT)
    ax.set_title(f'Price Comparison: {item_name}', color=COLOR_PRIMARY_ACCENT, fontsize=12, wrap=True)
    
    # Axis label colors
    ax.tick_params(axis='x', colors=COLOR_TEXT_DIM)
    ax.tick_params(axis='y', colors=COLOR_TEXT_DIM)
    
    # Add grid
    ax.yaxis.grid(True, color=COLOR_INPUT_BG, linestyle='-', linewidth=0.5)
    
    # Data labels above bars
    for bar in bars:
        yval = bar.get_height()
        # Determine text color based on profit/loss for the current price bar
        text_color = COLOR_TEXT_DIM
        if yval == current_price:
            if current_price >= buy_price:
                text_color = COLOR_PROFIT_GOOD
            else:
                text_color = COLOR_PROFIT_BAD
                
        ax.text(bar.get_x() + bar.get_width()/2.0, yval + (max(values)*0.01), f'{yval:.2f}$', 
                ha='center', va='bottom', 
                color=text_color,
                fontsize=10,
                weight='bold')
    
    # Set Y limit for better visualization
    ax.set_ylim(0, max(values) * 1.15 if max(values) > 0 else 1)


    # Create new window for chart
    chart_window = tk.Toplevel(root)
    chart_window.title(f"Price Chart: {item_name}")
    # --- SET FIXED WINDOW SIZE ---
    chart_window.geometry("650x600") 
    chart_window.resizable(False, False)
    # -----------------------------
    chart_window.configure(bg=COLOR_BG_DARK)
    
    # Place chart in Tkinter window
    canvas = FigureCanvasTkAgg(fig, master=chart_window)
    canvas_widget = canvas.get_tk_widget()
    canvas_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    fig.tight_layout()

def on_author_info():
    """Displays information about the author."""
    # Create the Author window
    author_window = tk.Toplevel(root)
    author_window.title("Author Information")
    author_window.geometry("350x200")
    author_window.resizable(False, False)
    author_window.configure(bg=COLOR_BG_DARK)
    
    try:
        author_window.attributes('-alpha', 0.90) 
    except tk.TclError:
        pass
        
    info_frame = ttk.Frame(author_window, style='TFrame', padding=(15,15,15,15), relief='solid', borderwidth=1)
    info_frame.pack(padx=20, pady=20, fill='both', expand=True)

    ttk.Label(info_frame, text="--- APPLICATION AUTHOR ---", 
              font=('Consolas', 12, 'bold'), foreground=COLOR_PRIMARY_ACCENT, 
              background=COLOR_BG_DARK).pack(pady=10)
    
    ttk.Label(info_frame, text="Application: Steam Market Portfolio", 
              font=('Consolas', 10), foreground=COLOR_TEXT_LIGHT, 
              background=COLOR_BG_DARK).pack(pady=2)
              
    ttk.Label(info_frame, text="Author: kucingsayabesar Aydar Gainullin", 
              font=('Consolas', 10), foreground=COLOR_SECONDARY_ACCENT, 
              background=COLOR_BG_DARK).pack(pady=2)
              
    ttk.Label(info_frame, text=f"Date: 12.10.2025", 
              font=('Consolas', 10), foreground=COLOR_TEXT_DIM, 
              background=COLOR_BG_DARK).pack(pady=2)

def on_import():
    """Handler for the import button."""
    path = filedialog.askopenfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")])
    if not path:
        return
        
    imported, updated = import_items_from_csv(path)
    
    refresh_table()
    messagebox.showinfo(
        "Import Complete", 
        f"Data successfully imported.\n"
        f"New items added: {imported}\n"
        f"Existing items updated: {updated}"
    )

def on_delete():
    sel = tree.selection()
    if not sel:
        messagebox.showwarning("Delete", "Select a row to delete")
        return
    vals = tree.item(sel[0])['values']
    if not vals or vals[1] == "Totals:":
        return
    try:
        item_id = int(vals[0])
    except ValueError:
        messagebox.showwarning("Error", "Invalid ID")
        return
    delete_item(item_id)
    refresh_table()
    messagebox.showinfo("Deleted", "Item deleted")

def on_row_double(event):
    sel = tree.selection()
    if not sel:
        return
    vals = tree.item(sel[0])['values']
    if not vals or vals[1] == "Totals:":
        return
        
    try:
        item_id = int(vals[0]) 
    except ValueError:
        return

    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT market_name, display_name, qty, buy_price, current_price FROM items WHERE id=?", (item_id,))
    r = c.fetchone()
    conn.close()
    if not r:
        return
        
    mname, dname, qty, buy, cur_steam = r
    
    # show item details window
    win = tk.Toplevel(root)
    # Используем market_name (mname) для заголовка
    win.title(mname) 
    win.geometry("400x300") 
    win.resizable(False, False) 
    win.configure(bg=COLOR_BG_DARK)
    
    try:
        win.attributes('-alpha', 0.90) 
    except tk.TclError:
        pass 

    info_frame = ttk.Frame(win, style='TFrame', padding=(15,15,15,15), relief='solid', borderwidth=1)
    info_frame.pack(padx=20, pady=20, fill='both', expand=True)

    ttk.Label(info_frame, text="--- ITEM INFORMATION ---", font=('Consolas', 12, 'bold'), foreground=COLOR_PRIMARY_ACCENT, background=COLOR_BG_DARK).pack(pady=10)
    
    # Используем market_name (mname) для отображения полного имени
    ttk.Label(info_frame, text=f"FULL NAME: {mname}", wraplength=350, font=('Consolas', 11, 'bold'), foreground=COLOR_PRIMARY_ACCENT, background=COLOR_BG_DARK).pack(pady=5)
    
    # display_name (если он очищен)
    if dname and dname != mname:
        ttk.Label(info_frame, text=f"CLEAN NAME: {dname}", wraplength=350, font=('Consolas', 9), foreground=COLOR_TEXT_DIM, background=COLOR_BG_DARK).pack(pady=2)

    ttk.Label(info_frame, text=f"QUANTITY: {qty}", font=('Consolas', 10), foreground=COLOR_SECONDARY_ACCENT, background=COLOR_BG_DARK).pack(pady=2)
    ttk.Label(info_frame, text=f"BUY PRICE (per unit AVG): {buy:.2f} USD", font=('Consolas', 10), foreground=COLOR_SECONDARY_ACCENT, background=COLOR_BG_DARK).pack(pady=2)
    
    ttk.Label(info_frame, text=f"CURRENT STEAM (per unit): {cur_steam:.2f} USD", font=('Consolas', 10), foreground=COLOR_PRIMARY_ACCENT, background=COLOR_BG_DARK).pack(pady=2)

    profit_val = (cur_steam * qty) - (buy * qty)
    profit_text = f"TOTAL PROFIT (STEAM): {profit_val:+.2f} USD"
    profit_color = COLOR_PROFIT_GOOD if profit_val >= 0 else COLOR_PROFIT_BAD
    
    ttk.Label(info_frame, text=profit_text, font=('Consolas', 11, 'bold'), foreground=profit_color, background=COLOR_BG_DARK).pack(pady=10)


# bindings
btn_fetch.config(command=on_fetch)
btn_add.config(command=on_add)
btn_update.config(command=on_update_all)
btn_import.config(command=on_import)      
btn_export_csv.config(command=on_export_csv) 
btn_export_html.config(command=on_export_html) 
btn_show_chart_selected.config(command=show_selected_item_chart) 
btn_author.config(command=on_author_info) 
btn_delete.config(command=on_delete) 
tree.bind("<Double-1>", on_row_double)

# initial table population
refresh_table()

if __name__ == '__main__':
    root.mainloop()