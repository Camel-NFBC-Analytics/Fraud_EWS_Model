import warnings
warnings.filterwarnings("ignore")

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import pandas as pd
import os
import threading

pd.set_option("display.max_columns", None)
pd.set_option("display.max_colwidth", None)


# ==================================================
# COMMON NORMALIZATION
# ==================================================
def normalize_columns(df):
    df = df.copy()
    df.columns = (
        df.columns
        .str.replace("ï»¿", "", regex=False)
        .str.strip()
        .str.lower()
    )
    return df


# ==================================================
# RULE 1 – UNIQUE CENTER PER BM PER DAY
# ==================================================
def apply_rule1(df):
    df = normalize_columns(df)

    required = [
        "state", "branch_name", "region_name",
        "attended by id", "month, day, year of meeting date", "center_id"
    ]
    for col in required:
        if col not in df.columns:
            raise ValueError(f"Missing column: {col}")

    df["month, day, year of meeting date"] = pd.to_datetime(
        df["month, day, year of meeting date"], errors="coerce"
    )

    df = df.drop_duplicates(
        subset=[
            "state", "branch_name", "region_name",
            "attended by id",
            "month, day, year of meeting date",
            "center_id"
        ]
    )

    pivot = pd.pivot_table(
        df,
        index=["state", "branch_name", "region_name", "attended by id"],
        columns="month, day, year of meeting date",
        values="center_id",
        aggfunc=pd.Series.nunique,
        fill_value=0
    ).reset_index()

    id_cols = ["state", "branch_name", "region_name", "attended by id"]
    date_cols = pivot.columns.difference(id_cols)

    pivot["Total"] = pivot[date_cols].sum(axis=1)
    pivot["Days_Visited"] = (pivot[date_cols] > 0).sum(axis=1)

    p97 = pivot["Days_Visited"].quantile(0.975)
    pivot["P97_5"] = p97
    pivot["Above_97_5"] = pivot["Days_Visited"] >= p97

    return pivot


# ==================================================
# RULE 2 – EXACT USER LOGIC
# ==================================================
def apply_rule2(df):
    df = normalize_columns(df)

    required = ["state", "branch_name", "cust_id", "loan_id", "lms_application_status"]
    for col in required:
        if col not in df.columns:
            raise ValueError(f"Missing column: {col}")

    df["lms_application_status"] = (
        df["lms_application_status"]
        .str.strip()
        .str.title()
    )

    df = df.drop_duplicates(
        subset=["state", "branch_name", "cust_id", "loan_id", "lms_application_status"]
    )

    pivot = pd.pivot_table(
        df,
        index=["state", "branch_name", "cust_id"],
        columns="lms_application_status",
        values="loan_id",
        aggfunc=pd.Series.nunique,
        fill_value=0
    ).reset_index()

    final_columns = [
        "state", "branch_name", "cust_id",
        "Active", "Bureau Check", "Cgt-1", "Draft",
        "Grt-1", "Pre Sanction", "Pre Sanction Verification",
        "Rejected", "Sanctioned"
    ]

    for col in final_columns:
        if col not in pivot.columns:
            pivot[col] = 0

    pivot = pivot[final_columns]

    status_cols = final_columns[3:]
    pivot["Grand Total"] = pivot[status_cols].sum(axis=1)

    pivot = pivot[pivot["Active"] > 0]
    pivot = pivot.sort_values("Rejected", ascending=False)

    pivot[status_cols + ["Grand Total"]] = (
        pivot[status_cols + ["Grand Total"]].replace(0, "")
    )

    return pivot


# ==================================================
# TKINTER UI
# ==================================================
class FraudRuleApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Fraud EWS – Automated Rule Tool")
        self.geometry("1100x650")
        self.configure(bg="#F4F6F7")

        self.df = None
        self.stop_flag = False

        self.create_ui()

    def create_ui(self):
    
        # ---------- WINDOW BACKGROUND ----------
        self.configure(bg="#EEF2F7")
    
        # ---------- HEADER ----------
        header = tk.Frame(self, bg="#1F4E79", height=65)
        header.pack(fill="x")
    
        tk.Label(
            header,
            text="Fraud EWS – Automated Rule Tool",
            bg="#1F4E79",
            fg="white",
            font=("Segoe UI", 18, "bold")
        ).pack(pady=14)
    
        # ---------- MAIN CARD ----------
        main = tk.Frame(
            self,
            bg="white",
            bd=1,
            relief="solid"
        )
        main.pack(padx=30, pady=25, fill="both", expand=True)
    
        # ---------- UPLOAD SECTION ----------
        upload_frame = tk.Frame(main, bg="white")
        upload_frame.pack(pady=10)
    
        upload_btn = tk.Button(
            upload_frame,
            text="📂 Upload CSV File",
            font=("Segoe UI", 11, "bold"),
            bg="#5DADE2",
            fg="white",
            activebackground="#3498DB",
            activeforeground="white",
            width=22,
            relief="flat",
            command=self.upload_file
        )
        upload_btn.pack(pady=5)
    
        self.file_label = tk.Label(
            upload_frame,
            text="No file selected",
            bg="white",
            fg="#7F8C8D",
            font=("Segoe UI", 9, "italic")
        )
        self.file_label.pack()
    
        # ---------- PREVIEW TITLE ----------
        tk.Label(
            main,
            text="Data Preview (Top 5 Rows)",
            bg="white",
            fg="#2C3E50",
            font=("Segoe UI", 10, "bold")
        ).pack(anchor="w", padx=10, pady=(15, 5))
    
        # ---------- PREVIEW TABLE ----------
        table_frame = tk.Frame(main, bg="white")
        table_frame.pack(fill="both", expand=True, padx=10)
    
        self.tree = ttk.Treeview(table_frame, show="headings")
        self.tree.pack(side="left", fill="both", expand=True)
    
        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(main, orient="horizontal", command=self.tree.xview)
    
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
    
        vsb.pack(side="right", fill="y")
        hsb.pack(fill="x", padx=10)
    
        # ---------- BUTTON STYLES ----------
        def styled_button(parent, text, bg, cmd):
            btn = tk.Button(
                parent,
                text=text,
                font=("Segoe UI", 10, "bold"),
                bg=bg,
                fg="white",
                width=14,
                relief="flat",
                activebackground=bg,
                activeforeground="white",
                command=cmd
            )
            btn.bind("<Enter>", lambda e: btn.config(bg="#34495E"))
            btn.bind("<Leave>", lambda e: btn.config(bg=bg))
            return btn
    
        # ---------- ACTION BUTTONS ----------
        btns = tk.Frame(main, bg="white")
        btns.pack(pady=15)
    
        styled_button(btns, "🚀 Rule 1", "#2E86C1", self.run_rule1).grid(row=0, column=0, padx=6)
        styled_button(btns, "⚡ Rule 2", "#17A589", self.run_rule2).grid(row=0, column=1, padx=6)
        styled_button(btns, "🔄 Reset", "#F39C12", self.reset_app).grid(row=0, column=2, padx=6)
        styled_button(btns, "⛔ Stop", "#C0392B", self.stop_processing).grid(row=0, column=3, padx=6)
    
        # ---------- STATUS BAR ----------
        self.status = tk.Label(
            main,
            text="Status: Waiting for file upload",
            bg="#F4F6F7",
            fg="#1F618D",
            font=("Segoe UI", 9, "italic"),
            anchor="w"
        )
        self.status.pack(fill="x", padx=5, pady=(10, 0))

    # ---------- FOOTER ----------
        footer = tk.Frame(self, bg="#1F4E79", height=30)
        footer.pack(fill="x", side="bottom")
        
        tk.Label(
            footer,
            text="Developed by Faiz Khan | Risk",
            bg="#1F4E79",
            fg="white",
            font=("Segoe UI", 9, "italic")
        ).pack(pady=6)


    # ------------------------------
    # FUNCTIONS
    # ------------------------------
    def upload_file(self):
        path = filedialog.askopenfilename(filetypes=[("CSV Files", "*.csv")])
        if not path:
            return

        self.df = pd.read_csv(path, encoding="latin1")
        self.file_label.config(text=os.path.basename(path), fg="black")
        self.status.config(text="Status: File uploaded successfully ✅")
        self.load_preview(self.df.head(5))

    def load_preview(self, df):
        self.tree.delete(*self.tree.get_children())
        self.tree["columns"] = list(df.columns)

        for col in df.columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=120, anchor="center")

        for _, row in df.iterrows():
            self.tree.insert("", "end", values=list(row))

    def save_output(self, df, name):
        path = filedialog.asksaveasfilename(defaultextension=".xlsx", initialfile=name)
        if path:
            df.to_excel(path, index=False)
            messagebox.showinfo("Success", "File saved successfully ✅")

    def run_rule1(self):
        try:
            self.status.config(text="Processing Rule 1...")
            res = apply_rule1(self.df)
            self.save_output(res, "Rule_1_Output.xlsx")
            self.status.config(text="Rule 1 completed ✅")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def run_rule2(self):
        try:
            self.status.config(text="Processing Rule 2...")
            res = apply_rule2(self.df)
            self.save_output(res, "Rule_2_Output.xlsx")
            self.status.config(text="Rule 2 completed ✅")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def reset_app(self):
        self.df = None
    
        # Clear table rows
        self.tree.delete(*self.tree.get_children())
    
        # 🔑 Clear table columns (this removes header view)
        self.tree["columns"] = ()
    
        self.file_label.config(text="No file selected", fg="gray")
        self.status.config(text="Status: Reset completed 🔄")


    def stop_processing(self):
        self.stop_flag = True
        self.status.config(text="Processing stopped ⛔")


# ==================================================
# START APP
# ==================================================
if __name__ == "__main__":
    app = FraudRuleApp()
    app.mainloop()
