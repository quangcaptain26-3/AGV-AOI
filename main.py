import customtkinter as ctk
from tkinter import filedialog
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import pandas as pd
import aoi
import agv

# Cấu hình UI Hiện đại
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class DashboardApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("AGV & AOI Monitoring Dashboard")
        self.geometry("1200x800")

        self.selected_log_files = []
        self.selected_image_files = []
        self.df_offline = pd.DataFrame()
        self.df_api = pd.DataFrame()
        self.df_aoi = pd.DataFrame()
        self.coverage = None
        self._mpl_hover_cleanup = []
        
        # --- HEADER ---
        self.header_frame = ctk.CTkFrame(self, height=60, corner_radius=0)
        self.header_frame.pack(fill="x", side="top")
        
        self.title_label = ctk.CTkLabel(self.header_frame, text="HỆ THỐNG GIÁM SÁT VẬN HÀNH & CHẤT LƯỢNG", font=ctk.CTkFont(size=20, weight="bold"))
        self.title_label.pack(side="left", padx=20, pady=15)
        
        self.header_actions = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        self.header_actions.pack(side="right", padx=20, pady=12)

        self.btn_load_logs = ctk.CTkButton(self.header_actions, text="Chọn file Log AGV", command=self.load_agv_logs)
        self.btn_load_logs.pack(side="left", padx=(0, 10))

        self.btn_load_images = ctk.CTkButton(self.header_actions, text="Chọn file Ảnh AOI", command=self.load_aoi_images)
        self.btn_load_images.pack(side="left")

        # --- GRID LAYOUT (3x3) ---
        self.grid_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.grid_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.grid_frame.columnconfigure((0, 1, 2), weight=1)
        self.grid_frame.rowconfigure((0, 1, 2), weight=1)

        # Tổng quan nhanh: trải ngang full để không bị co
        self.frame_kpi = self.create_chart_frame(0, 0, "Tổng quan nhanh", colspan=3)

        # Hàng 2: trend + heatmap (nhiều thông tin, cần rộng)
        self.frame_offline_trend = self.create_chart_frame(1, 0, "Xu hướng AGV rớt mạng (Trend + Heatmap)", colspan=2)
        self.frame_api_trend = self.create_chart_frame(1, 2, "Xu hướng lỗi API (Trend + Heatmap)")

        # Hàng 3: charts tóm tắt
        self.frame_agv = self.create_chart_frame(2, 0, "Top AGV rớt mạng")
        self.frame_aoi = self.create_chart_frame(2, 1, "AOI Pass/Fail theo ngày")
        self.frame_aoi_rate = self.create_chart_frame(2, 2, "AOI Pass rate (%) theo ngày")

        # KPI content
        self.kpi_box = ctk.CTkFrame(self.frame_kpi, fg_color="transparent")
        self.kpi_box.pack(fill="both", expand=True, padx=10, pady=10)
        self.kpi_box.columnconfigure((0, 1), weight=1, uniform="kpi")
        self.kpi_box.rowconfigure((0, 1), weight=1, uniform="kpi")

        self.kpi_cards = {}
        self.kpi_cards["agv"] = self._create_kpi_card(self.kpi_box, 0, 0, "AGV Offline", "—", "Chưa có log")
        self.kpi_cards["api"] = self._create_kpi_card(self.kpi_box, 0, 1, "API Errors", "—", "Chưa có log")
        self.kpi_cards["aoi"] = self._create_kpi_card(self.kpi_box, 1, 0, "AOI Yield", "—", "Chưa có ảnh")
        self.kpi_cards["cover"] = self._create_kpi_card(self.kpi_box, 1, 1, "Coverage", "—", "Chưa có dữ liệu")

        self.update_header_status()
        self.update_kpi()

    def create_chart_frame(self, row, col, title, colspan=1, rowspan=1):
        frame = ctk.CTkFrame(self.grid_frame, corner_radius=10)
        frame.grid(row=row, column=col, padx=10, pady=10, sticky="nsew", columnspan=colspan, rowspan=rowspan)
        label = ctk.CTkLabel(frame, text=title, font=ctk.CTkFont(size=15, weight="bold"))
        label.pack(pady=(10, 0))
        return frame

    def _create_kpi_card(self, parent, row, col, title, value, subtitle):
        card = ctk.CTkFrame(parent, corner_radius=12)
        card.grid(row=row, column=col, padx=6, pady=6, sticky="nsew")
        lbl_title = ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=13, weight="bold"))
        lbl_title.pack(anchor="w", padx=10, pady=(8, 0))
        lbl_value = ctk.CTkLabel(card, text=value, font=ctk.CTkFont(size=28, weight="bold"))
        lbl_value.pack(anchor="w", padx=10, pady=(2, 0))
        lbl_sub = ctk.CTkLabel(card, text=subtitle, font=ctk.CTkFont(size=12), text_color="#cfcfcf", justify="left")
        lbl_sub.pack(anchor="w", padx=10, pady=(2, 8))
        return {"frame": card, "title": lbl_title, "value": lbl_value, "sub": lbl_sub}

    def _set_kpi_style(self, key, level):
        # level: ok / warn / alert / neutral
        palette = {
            "ok": ("#1f8b4c", "#eafff2"),
            "warn": ("#b07d00", "#fff6df"),
            "alert": ("#b00020", "#ffe6ea"),
            "neutral": ("#3b3b3b", "#ffffff"),
        }
        bg, fg = palette.get(level, palette["neutral"])
        self.kpi_cards[key]["frame"].configure(fg_color=bg)
        self.kpi_cards[key]["value"].configure(text_color=fg)
        self.kpi_cards[key]["title"].configure(text_color=fg)

    def update_header_status(self):
        log_part = f"Log AGV: {len(self.selected_log_files)} file" if self.selected_log_files else "Log AGV: chưa chọn"
        img_part = f"Ảnh AOI: {len(self.selected_image_files)} file" if self.selected_image_files else "Ảnh AOI: chưa chọn"
        self.title_label.configure(text=f"{log_part} | {img_part}")

    def load_agv_logs(self):
        file_paths = filedialog.askopenfilenames(
            title="Chọn file log AGV (.txt)",
            filetypes=[("Text logs", "*.txt"), ("All files", "*.*")],
        )
        if not file_paths:
            return

        self.selected_log_files = list(file_paths)
        self.update_header_status()

        try:
            df_offline, df_api, system_events, coverage = agv.parse_agv_logs(self.selected_log_files)
        except Exception as e:
            self.df_offline = pd.DataFrame()
            self.df_api = pd.DataFrame()
            self.coverage = None
            self.draw_agv_chart(self.df_offline)
            self.draw_api_chart(self.df_api)
            self.draw_offline_trend(self.df_offline)
            self.update_kpi()
            return

        self.df_offline = df_offline
        self.df_api = df_api
        self.coverage = coverage

        self.draw_agv_chart(self.df_offline)
        self.draw_api_chart(self.df_api)
        self.draw_offline_trend(self.df_offline)
        self.update_kpi()

        # Không còn khung nhật ký; cảnh báo sẽ dồn vào KPI/biểu đồ (rỗng)

    def load_aoi_images(self):
        file_paths = filedialog.askopenfilenames(
            title="Chọn file ảnh AOI",
            filetypes=[
                ("Images", "*.png *.jpg *.jpeg *.bmp"),
                ("PNG", "*.png"),
                ("JPG", "*.jpg *.jpeg"),
                ("BMP", "*.bmp"),
                ("All files", "*.*"),
            ],
        )
        if not file_paths:
            return

        self.selected_image_files = list(file_paths)
        self.update_header_status()

        self.df_aoi = aoi.parse_aoi_images(self.selected_image_files)
        self.draw_aoi_chart(self.df_aoi)
        self.draw_aoi_rate_chart(self.df_aoi)
        self.update_kpi()

    def draw_matplot(self, frame, fig):
        # Xóa biểu đồ cũ nếu có
        for widget in frame.winfo_children():
            if isinstance(widget, ctk.CTkLabel): continue
            widget.destroy()
        
        # Nhúng Matplotlib vào Tkinter
        canvas = FigureCanvasTkAgg(fig, master=frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=5, pady=5)
        return canvas

    def setup_dark_plot(self, ax, fig):
        # Định dạng biểu đồ hợp với Dark Mode
        bg_color = "#2b2b2b"
        text_color = "white"
        fig.patch.set_facecolor(bg_color)
        ax.set_facecolor(bg_color)
        ax.tick_params(colors=text_color)
        ax.xaxis.label.set_color(text_color)
        ax.yaxis.label.set_color(text_color)
        ax.spines['bottom'].set_color(text_color)
        ax.spines['left'].set_color(text_color)
        for spine in ['top', 'right']: ax.spines[spine].set_visible(False)

    def draw_agv_chart(self, df):
        fig, ax = plt.subplots(figsize=(5, 3))
        self.setup_dark_plot(ax, fig)
        if df is not None and not df.empty:
            top = (
                df.groupby('AGV', as_index=False)['Count']
                .sum()
                .sort_values('Count', ascending=False)
                .head(10)
            )
            ax.bar(top['AGV'].astype(str), top['Count'], color='#e74c3c')
            ax.set_xlabel("AGV")
            ax.set_ylabel("Số lần rớt mạng")
        canvas = self.draw_matplot(self.frame_agv, fig)
        self._enable_bar_hover(canvas, ax, title="Top AGV rớt mạng", x_label="AGV", y_label="Số lần rớt mạng")

    def draw_offline_trend(self, df):
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(8, 3))
        self.setup_dark_plot(ax1, fig)
        ax2.set_facecolor("#2b2b2b")
        ax2.tick_params(colors="white")
        for spine in ['top', 'right']:
            ax2.spines[spine].set_visible(False)
        ax2.spines['bottom'].set_color("white")
        ax2.spines['left'].set_color("white")

        if df is not None and not df.empty:
            # Trend tổng theo mốc giờ (dd/mm HH:00)
            trend = df.groupby('Hour', as_index=False)['Count'].sum()
            ax1.plot(trend['Hour'], trend['Count'], marker='o', color='#e74c3c', label='Offline')
            ax1.legend(facecolor='#2b2b2b', labelcolor='white')
            ax1.tick_params(axis='x', rotation=45)

            # Heatmap theo ngày / giờ trong ngày (nhìn nhanh giờ cao điểm)
            tmp = trend.copy()
            tmp['Day'] = tmp['Hour'].str.slice(0, 5)   # dd/mm
            tmp['H'] = tmp['Hour'].str.slice(6, 8)     # HH
            heat = tmp.pivot_table(index='Day', columns='H', values='Count', aggfunc='sum', fill_value=0)
            im = ax2.imshow(heat.values, aspect='auto', interpolation='nearest', cmap='magma')
            ax2.set_title("Heatmap", color="white", fontsize=10)
            ax2.set_yticks(range(len(heat.index)))
            ax2.set_yticklabels(list(heat.index), color="white", fontsize=8)
            ax2.set_xticks(range(len(heat.columns)))
            ax2.set_xticklabels(list(heat.columns), color="white", fontsize=8, rotation=0)
            fig.colorbar(im, ax=ax2, fraction=0.046, pad=0.04)

        fig.tight_layout()
        canvas = self.draw_matplot(self.frame_offline_trend, fig)
        self._enable_line_hover(canvas, ax1, title="Xu hướng AGV rớt mạng", x_label="Mốc giờ", y_label="Số lần rớt mạng (tổng)")
        if df is not None and not df.empty:
            self._enable_heatmap_hover(
                canvas,
                ax2,
                im,
                heat,
                title="Heatmap rớt mạng",
                meaning="Mỗi ô là tổng số lần rớt mạng trong 1 giờ (theo ngày/giờ).",
                value_label="Offline",
            )

    def draw_aoi_chart(self, df):
        fig, ax = plt.subplots(figsize=(5, 3))
        self.setup_dark_plot(ax, fig)
        if not df.empty:
            ax.bar(df['Date'], df['PASS'], color='#2ecc71', label='ALL PASS')
            ax.bar(df['Date'], df['FAIL'], bottom=df['PASS'], color='#e74c3c', label='FAIL')
            ax.legend(facecolor='#2b2b2b', labelcolor='white')
            plt.xticks(rotation=45)
        canvas = self.draw_matplot(self.frame_aoi, fig)
        self._enable_aoi_hover(canvas, ax, df)

    def draw_aoi_rate_chart(self, df):
        fig, ax = plt.subplots(figsize=(5, 3))
        self.setup_dark_plot(ax, fig)
        if df is not None and not df.empty and ('PASS' in df.columns) and ('FAIL' in df.columns):
            total = (df['PASS'] + df['FAIL']).replace(0, pd.NA)
            rate = (df['PASS'] / total * 100).fillna(0)
            ax.plot(df['Date'], rate, marker='o', color='#2ecc71', label='Pass rate (%)')
            ax.set_ylim(0, 100)
            ax.legend(facecolor='#2b2b2b', labelcolor='white')
            plt.xticks(rotation=45)
        canvas = self.draw_matplot(self.frame_aoi_rate, fig)
        self._enable_aoi_rate_hover(canvas, ax, df)

    def draw_api_chart(self, df):
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(8, 3))
        self.setup_dark_plot(ax1, fig)
        ax2.set_facecolor("#2b2b2b")
        ax2.tick_params(colors="white")
        for spine in ['top', 'right']:
            ax2.spines[spine].set_visible(False)
        ax2.spines['bottom'].set_color("white")
        ax2.spines['left'].set_color("white")

        if df is not None and not df.empty and 'Hour' in df.columns:
            # Trend tổng lỗi API theo mốc giờ
            trend = df.groupby('Hour', as_index=False)['Count'].sum()
            ax1.plot(trend['Hour'], trend['Count'], marker='o', color='#f39c12', label='API errors')
            ax1.legend(facecolor='#2b2b2b', labelcolor='white')
            ax1.tick_params(axis='x', rotation=45)

            # Heatmap theo ngày/giờ (tổng lỗi API)
            tmp = trend.copy()
            tmp['Day'] = tmp['Hour'].str.slice(0, 5)   # dd/mm
            tmp['H'] = tmp['Hour'].str.slice(6, 8)     # HH
            heat = tmp.pivot_table(index='Day', columns='H', values='Count', aggfunc='sum', fill_value=0)
            im = ax2.imshow(heat.values, aspect='auto', interpolation='nearest', cmap='viridis')
            ax2.set_title("Heatmap", color="white", fontsize=10)
            ax2.set_yticks(range(len(heat.index)))
            ax2.set_yticklabels(list(heat.index), color="white", fontsize=8)
            ax2.set_xticks(range(len(heat.columns)))
            ax2.set_xticklabels(list(heat.columns), color="white", fontsize=8, rotation=0)
            fig.colorbar(im, ax=ax2, fraction=0.046, pad=0.04)

        fig.tight_layout()
        canvas = self.draw_matplot(self.frame_api_trend, fig)
        self._enable_line_hover(canvas, ax1, title="Xu hướng lỗi API", x_label="Mốc giờ", y_label="Số lỗi API (tổng)")
        if df is not None and not df.empty and 'Hour' in df.columns:
            self._enable_heatmap_hover(
                canvas,
                ax2,
                im,
                heat,
                title="Heatmap lỗi API",
                meaning="Mỗi ô là tổng số lỗi API trong 1 giờ (theo ngày/giờ).",
                value_label="API errors",
            )

    def update_kpi(self):
        # --- AGV OFFLINE KPI ---
        offline_total = int(self.df_offline['Count'].sum()) if self.df_offline is not None and not self.df_offline.empty and 'Count' in self.df_offline.columns else 0
        agv_affected = int(self.df_offline['AGV'].nunique()) if self.df_offline is not None and not self.df_offline.empty and 'AGV' in self.df_offline.columns else 0
        offline_last = 0
        offline_prev = 0
        peak_hour = None
        peak_val = 0
        top_agv = None
        top_agv_val = 0
        if self.df_offline is not None and not self.df_offline.empty and 'Hour' in self.df_offline.columns:
            trend = self.df_offline.groupby('Hour', as_index=False)['Count'].sum()
            trend = trend.sort_values('Hour')
            if len(trend) >= 1:
                offline_last = int(trend.iloc[-1]['Count'])
            if len(trend) >= 2:
                offline_prev = int(trend.iloc[-2]['Count'])
            peak_row = trend.loc[trend['Count'].idxmax()] if not trend.empty else None
            if peak_row is not None:
                peak_hour = str(peak_row['Hour'])
                peak_val = int(peak_row['Count'])

            top = self.df_offline.groupby('AGV', as_index=False)['Count'].sum().sort_values('Count', ascending=False)
            if not top.empty:
                top_agv = str(top.iloc[0]['AGV'])
                top_agv_val = int(top.iloc[0]['Count'])

        delta_off = offline_last - offline_prev
        delta_txt = f"{'+' if delta_off >= 0 else ''}{delta_off} vs giờ trước" if (offline_last or offline_prev) else "—"
        agv_sub = (
            f"Ảnh hưởng: {agv_affected} AGV\n"
            f"Cao điểm: {peak_val} lần @ {peak_hour if peak_hour else '—'}\n"
            f"Nặng nhất: AGV {top_agv if top_agv else '—'} ({top_agv_val} lần)\n"
            f"Giờ gần nhất: {offline_last} lần ({self._fmt_delta(delta_off)} vs giờ trước)"
        )
        if offline_total == 0:
            self._kpi_set("agv", str(offline_total), agv_sub, "ok")
        elif offline_last >= 10 or peak_val >= 20:
            self._kpi_set("agv", str(offline_total), agv_sub, "alert")
        else:
            self._kpi_set("agv", str(offline_total), agv_sub, "warn")

        # --- API KPI ---
        api_total = int(self.df_api['Count'].sum()) if self.df_api is not None and not self.df_api.empty and 'Count' in self.df_api.columns else 0
        api_last = 0
        api_prev = 0
        top_api = None
        top_api_val = 0
        if self.df_api is not None and not self.df_api.empty and 'Hour' in self.df_api.columns:
            trend_api = self.df_api.groupby('Hour', as_index=False)['Count'].sum().sort_values('Hour')
            if len(trend_api) >= 1:
                api_last = int(trend_api.iloc[-1]['Count'])
            if len(trend_api) >= 2:
                api_prev = int(trend_api.iloc[-2]['Count'])
            if 'API' in self.df_api.columns:
                topa = self.df_api.groupby('API', as_index=False)['Count'].sum().sort_values('Count', ascending=False)
                if not topa.empty:
                    top_api = str(topa.iloc[0]['API'])
                    top_api_val = int(topa.iloc[0]['Count'])
        delta_api = api_last - api_prev
        delta_api_txt = f"{'+' if delta_api >= 0 else ''}{delta_api} vs giờ trước" if (api_last or api_prev) else "—"
        api_sub = (
            f"Lỗi nhiều nhất: {top_api if top_api else '—'} ({top_api_val} lần)\n"
            f"Giờ gần nhất: {api_last} lần ({self._fmt_delta(delta_api)} vs giờ trước)"
        )
        if api_total == 0:
            self._kpi_set("api", str(api_total), api_sub, "ok")
        elif api_last >= 10:
            self._kpi_set("api", str(api_total), api_sub, "alert")
        else:
            self._kpi_set("api", str(api_total), api_sub, "warn")

        # --- AOI KPI ---
        aoi_pass = int(self.df_aoi['PASS'].sum()) if self.df_aoi is not None and not self.df_aoi.empty and 'PASS' in self.df_aoi.columns else 0
        aoi_fail = int(self.df_aoi['FAIL'].sum()) if self.df_aoi is not None and not self.df_aoi.empty and 'FAIL' in self.df_aoi.columns else 0
        aoi_total = aoi_pass + aoi_fail
        aoi_rate = (aoi_pass / aoi_total * 100) if aoi_total > 0 else 0.0
        worst_day = None
        worst_fail = 0
        last_rate = None
        prev_rate = None
        if self.df_aoi is not None and not self.df_aoi.empty and ('Date' in self.df_aoi.columns):
            tmp = self.df_aoi.copy()
            tmp['TOTAL'] = tmp.get('PASS', 0) + tmp.get('FAIL', 0)
            tmp['FAIL_RATE'] = (tmp.get('FAIL', 0) / tmp['TOTAL'].replace(0, pd.NA) * 100).fillna(0)
            wd = tmp.sort_values('FAIL_RATE', ascending=False).head(1)
            if not wd.empty:
                worst_day = str(wd.iloc[0]['Date'])
                worst_fail = float(wd.iloc[0]['FAIL_RATE'])
            tmp_sorted = tmp.sort_values('Date')
            if len(tmp_sorted) >= 1:
                last_rate = float(100 - tmp_sorted.iloc[-1]['FAIL_RATE'])
            if len(tmp_sorted) >= 2:
                prev_rate = float(100 - tmp_sorted.iloc[-2]['FAIL_RATE'])
        delta_yield = (last_rate - prev_rate) if (last_rate is not None and prev_rate is not None) else None
        delta_yield_txt = f"{'+' if delta_yield >= 0 else ''}{delta_yield:.1f}pp vs ngày trước" if delta_yield is not None else "—"
        aoi_sub = (
            f"Tổng: {aoi_total} ảnh\n"
            f"PASS: {aoi_pass} | FAIL: {aoi_fail}\n"
            f"Tệ nhất: {worst_day if worst_day else '—'} ({worst_fail:.1f}% fail)\n"
            f"So với ngày trước: {delta_yield_txt}"
        )
        if aoi_total == 0:
            self._kpi_set("aoi", "—", aoi_sub, "neutral")
        elif aoi_rate >= 98:
            self._kpi_set("aoi", f"{aoi_rate:.1f}%", aoi_sub, "ok")
        elif aoi_rate >= 95:
            self._kpi_set("aoi", f"{aoi_rate:.1f}%", aoi_sub, "warn")
        else:
            self._kpi_set("aoi", f"{aoi_rate:.1f}%", aoi_sub, "alert")

        # --- COVERAGE KPI (dựa TS_MIN/TS_MAX từ parser) ---
        ts_min = None
        ts_max = None
        files_n = len(self.selected_log_files)
        if isinstance(self.coverage, dict):
            ts_min = self.coverage.get("ts_min")
            ts_max = self.coverage.get("ts_max")
            files_n = int(self.coverage.get("files", files_n))

        if ts_min is not None and ts_max is not None:
            span = ts_max - ts_min
            hours = span.total_seconds() / 3600 if hasattr(span, "total_seconds") else 0
            cover_value = f"{hours:.1f}h"
            cover_sub = f"Từ: {pd.to_datetime(ts_min).strftime('%Y-%m-%d %H:%M:%S')}\nĐến: {pd.to_datetime(ts_max).strftime('%Y-%m-%d %H:%M:%S')}\nLog files: {files_n}"
            self._kpi_set("cover", cover_value, cover_sub, "neutral")
        else:
            self._kpi_set(
                "cover",
                "—",
                f"Log: {files_n} file | Ảnh: {len(self.selected_image_files)} file",
                "neutral",
            )

    def _fmt_delta(self, delta, unit=""):
        if delta is None:
            return "—"
        sign = "+" if delta >= 0 else ""
        return f"{sign}{delta}{unit}"

    def _fmt_delta_float(self, delta, unit=""):
        if delta is None:
            return "—"
        sign = "+" if delta >= 0 else ""
        return f"{sign}{delta:.1f}{unit}"

    def _kpi_set(self, key, value, subtitle, level="neutral"):
        self.kpi_cards[key]["value"].configure(text=value)
        self.kpi_cards[key]["sub"].configure(text=subtitle)
        self._set_kpi_style(key, level)

    def _enable_heatmap_hover(self, canvas, ax, im, heat_df, title, meaning, value_label):
        annot = ax.annotate(
            "",
            xy=(0, 0),
            xytext=(10, 10),
            textcoords="offset points",
            bbox=dict(boxstyle="round,pad=0.35", fc="#111111", ec="#bbbbbb", alpha=0.95),
            color="white",
            annotation_clip=False,
        )
        annot.set_visible(False)

        rows = list(heat_df.index)
        cols = list(heat_df.columns)

        def on_move(event):
            if event.inaxes != ax or event.xdata is None or event.ydata is None:
                if annot.get_visible():
                    annot.set_visible(False)
                    canvas.draw_idle()
                return

            x = int(round(event.xdata))
            y = int(round(event.ydata))
            if y < 0 or y >= len(rows) or x < 0 or x >= len(cols):
                if annot.get_visible():
                    annot.set_visible(False)
                    canvas.draw_idle()
                return

            val = heat_df.iloc[y, x]
            annot.xy = (x, y)
            # Né biên: nếu chuột gần mép trên thì đẩy tooltip xuống dưới
            xoff = 10 if (event.x or 0) < 500 else -220
            yoff = -90 if (event.y or 0) > 260 else 10
            annot.set_position((xoff, yoff))
            annot.set_text(
                f"{title}\n"
                f"{meaning}\n\n"
                f"Ngày: {rows[y]}\n"
                f"Giờ: {cols[x]}:00\n"
                f"{value_label}: {int(val)}"
            )
            annot.set_visible(True)
            canvas.draw_idle()

        cid = canvas.mpl_connect("motion_notify_event", on_move)
        self._mpl_hover_cleanup.append((canvas, cid))

    def _enable_line_hover(self, canvas, ax, title, x_label, y_label):
        lines = ax.get_lines()
        if not lines:
            return
        line = lines[0]
        xdata = list(line.get_xdata())
        ydata = list(line.get_ydata())

        annot = ax.annotate(
            "",
            xy=(0, 0),
            xytext=(10, 10),
            textcoords="offset points",
            bbox=dict(boxstyle="round,pad=0.35", fc="#111111", ec="#bbbbbb", alpha=0.95),
            color="white",
            annotation_clip=False,
        )
        annot.set_visible(False)

        def on_move(event):
            if event.inaxes != ax:
                if annot.get_visible():
                    annot.set_visible(False)
                    canvas.draw_idle()
                return

            contains, info = line.contains(event)
            if not contains or not info.get("ind"):
                if annot.get_visible():
                    annot.set_visible(False)
                    canvas.draw_idle()
                return

            idx = info["ind"][0]
            x = xdata[idx]
            y = ydata[idx]
            annot.xy = (x, y)
            xoff = 10 if (event.x or 0) < 500 else -200
            yoff = -70 if (event.y or 0) > 260 else 10
            annot.set_position((xoff, yoff))
            annot.set_text(
                f"{title}\n"
                f"{x_label}: {x}\n"
                f"{y_label}: {int(y) if float(y).is_integer() else y}"
            )
            annot.set_visible(True)
            canvas.draw_idle()

        cid = canvas.mpl_connect("motion_notify_event", on_move)
        self._mpl_hover_cleanup.append((canvas, cid))

    def _enable_bar_hover(self, canvas, ax, title, x_label, y_label):
        bars = [p for p in ax.patches if hasattr(p, "get_height")]
        if not bars:
            return

        annot = ax.annotate(
            "",
            xy=(0, 0),
            xytext=(10, 10),
            textcoords="offset points",
            bbox=dict(boxstyle="round,pad=0.35", fc="#111111", ec="#bbbbbb", alpha=0.95),
            color="white",
            annotation_clip=False,
        )
        annot.set_visible(False)

        def on_move(event):
            if event.inaxes != ax:
                if annot.get_visible():
                    annot.set_visible(False)
                    canvas.draw_idle()
                return

            for b in bars:
                contains, _ = b.contains(event)
                if contains:
                    x = b.get_x() + b.get_width() / 2
                    y = b.get_height()
                    annot.xy = (x, y)
                    # Nếu cột nằm vùng cao của chart, đẩy tooltip xuống dưới để không đè tiêu đề
                    y_max = ax.get_ylim()[1] if ax.get_ylim() else 1
                    high_zone = y >= (0.7 * y_max)
                    xoff = 10 if (event.x or 0) < 500 else -170
                    yoff = -70 if high_zone else 10
                    annot.set_position((xoff, yoff))
                    label = ax.get_xticklabels()
                    idx = bars.index(b) if bars.index(b) < len(label) else None
                    xval = label[idx].get_text() if idx is not None else ""
                    annot.set_text(
                        f"{title}\n"
                        f"{x_label}: {xval}\n"
                        f"{y_label}: {int(y)}"
                    )
                    annot.set_visible(True)
                    canvas.draw_idle()
                    return

            if annot.get_visible():
                annot.set_visible(False)
                canvas.draw_idle()

        cid = canvas.mpl_connect("motion_notify_event", on_move)
        self._mpl_hover_cleanup.append((canvas, cid))

    def _enable_stacked_bar_hover(self, canvas, ax, title, x_label, series_labels):
        bars = [p for p in ax.patches if hasattr(p, "get_height")]
        if not bars:
            return

        annot = ax.annotate(
            "",
            xy=(0, 0),
            xytext=(10, 10),
            textcoords="offset points",
            bbox=dict(boxstyle="round,pad=0.35", fc="#111111", ec="#bbbbbb", alpha=0.95),
            color="white",
            annotation_clip=False,
        )
        annot.set_visible(False)

        def on_move(event):
            if event.inaxes != ax:
                if annot.get_visible():
                    annot.set_visible(False)
                    canvas.draw_idle()
                return

            xticks = [t.get_text() for t in ax.get_xticklabels()]
            n = len(xticks) if xticks else 0
            if n == 0:
                return

            for i, b in enumerate(bars):
                contains, _ = b.contains(event)
                if not contains:
                    continue
                # 2 series (PASS/FAIL) stacked theo thứ tự vẽ
                series = series_labels[0] if i < n else series_labels[1] if len(series_labels) > 1 else "Value"
                col_idx = i if i < n else i - n
                xval = xticks[col_idx] if col_idx < len(xticks) else ""
                y = b.get_height()
                annot.xy = (b.get_x() + b.get_width() / 2, b.get_y() + y)
                xoff = 10 if (event.x or 0) < 500 else -190
                yoff = -70 if (event.y or 0) > 260 else 10
                annot.set_position((xoff, yoff))
                annot.set_text(
                    f"{title}\n"
                    f"{x_label}: {xval}\n"
                    f"{series}: {int(y)}"
                )
                annot.set_visible(True)
                canvas.draw_idle()
                return

            if annot.get_visible():
                annot.set_visible(False)
                canvas.draw_idle()

        cid = canvas.mpl_connect("motion_notify_event", on_move)
        self._mpl_hover_cleanup.append((canvas, cid))

    def _enable_aoi_hover(self, canvas, ax, df):
        """
        Hover cho chart AOI Pass/Fail:
        - Hiển thị Date, PASS, FAIL, Total, Yield (%)
        """
        if df is None or df.empty or 'Date' not in df.columns:
            return

        local = df.copy()
        local['PASS'] = local.get('PASS', 0)
        local['FAIL'] = local.get('FAIL', 0)
        local['TOTAL'] = local['PASS'] + local['FAIL']
        local['YIELD'] = (local['PASS'] / local['TOTAL'].replace(0, pd.NA) * 100).fillna(0)
        by_date = {str(r['Date']): r for _, r in local.iterrows()}

        bars = [p for p in ax.patches if hasattr(p, "get_height")]
        if not bars:
            return

        annot = ax.annotate(
            "",
            xy=(0, 0),
            xytext=(10, 10),
            textcoords="offset points",
            bbox=dict(boxstyle="round,pad=0.35", fc="#111111", ec="#bbbbbb", alpha=0.95),
            color="white",
            annotation_clip=False,
        )
        annot.set_visible(False)

        def on_move(event):
            if event.inaxes != ax:
                if annot.get_visible():
                    annot.set_visible(False)
                    canvas.draw_idle()
                return

            xticks = [t.get_text() for t in ax.get_xticklabels()]
            n = len(xticks)
            if n == 0:
                return

            for i, b in enumerate(bars):
                contains, _ = b.contains(event)
                if not contains:
                    continue

                col_idx = i if i < n else i - n
                date = xticks[col_idx] if col_idx < len(xticks) else ""
                row = by_date.get(date)
                if row is None:
                    return

                series = "PASS" if i < n else "FAIL"
                val = int(b.get_height())
                annot.xy = (b.get_x() + b.get_width() / 2, b.get_y() + b.get_height())
                xoff = 10 if (event.x or 0) < 500 else -280
                yoff = -120 if (event.y or 0) > 260 else 10
                annot.set_position((xoff, yoff))
                annot.set_text(
                    "AOI Pass/Fail theo ngày\n"
                    "Ý nghĩa: số lượng ảnh PASS/FAIL theo ngày.\n\n"
                    f"Ngày: {date}\n"
                    f"{series}: {val}\n"
                    f"PASS: {int(row['PASS'])} | FAIL: {int(row['FAIL'])} | Tổng: {int(row['TOTAL'])}\n"
                    f"Yield (PASS/Tổng): {float(row['YIELD']):.1f}%"
                )
                annot.set_visible(True)
                canvas.draw_idle()
                return

            if annot.get_visible():
                annot.set_visible(False)
                canvas.draw_idle()

        cid = canvas.mpl_connect("motion_notify_event", on_move)
        self._mpl_hover_cleanup.append((canvas, cid))

    def _enable_aoi_rate_hover(self, canvas, ax, df):
        """
        Hover cho đường Pass rate:
        - Hiển thị Date, Pass rate, Total/PASS/FAIL (nếu có)
        """
        lines = ax.get_lines()
        if not lines:
            return

        line = lines[0]
        xdata = list(line.get_xdata())
        ydata = list(line.get_ydata())

        by_date = {}
        if df is not None and not df.empty and 'Date' in df.columns:
            local = df.copy()
            local['PASS'] = local.get('PASS', 0)
            local['FAIL'] = local.get('FAIL', 0)
            local['TOTAL'] = local['PASS'] + local['FAIL']
            for _, r in local.iterrows():
                by_date[str(r['Date'])] = r

        annot = ax.annotate(
            "",
            xy=(0, 0),
            xytext=(10, 10),
            textcoords="offset points",
            bbox=dict(boxstyle="round,pad=0.35", fc="#111111", ec="#bbbbbb", alpha=0.95),
            color="white",
            annotation_clip=False,
        )
        annot.set_visible(False)

        def on_move(event):
            if event.inaxes != ax:
                if annot.get_visible():
                    annot.set_visible(False)
                    canvas.draw_idle()
                return

            contains, info = line.contains(event)
            if not contains or not info.get("ind"):
                if annot.get_visible():
                    annot.set_visible(False)
                    canvas.draw_idle()
                return

            idx = info["ind"][0]
            date = str(xdata[idx])
            rate = float(ydata[idx])
            annot.xy = (xdata[idx], ydata[idx])
            xoff = 10 if (event.x or 0) < 500 else -260
            yoff = -100 if (event.y or 0) > 260 else 10
            annot.set_position((xoff, yoff))

            extra = ""
            r = by_date.get(date)
            if r is not None:
                extra = f"\nPASS: {int(r['PASS'])} | FAIL: {int(r['FAIL'])} | Tổng: {int(r['TOTAL'])}"

            annot.set_text(
                "AOI Pass rate (%)\n"
                "Ý nghĩa: tỷ lệ PASS/Tổng theo ngày.\n\n"
                f"Ngày: {date}\n"
                f"Pass rate: {rate:.1f}%"
                f"{extra}"
            )
            annot.set_visible(True)
            canvas.draw_idle()

        cid = canvas.mpl_connect("motion_notify_event", on_move)
        self._mpl_hover_cleanup.append((canvas, cid))

if __name__ == "__main__":
    app = DashboardApp()
    app.mainloop()