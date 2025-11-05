from playwright.sync_api import sync_playwright
import pandas as pd
from datetime import datetime, timedelta, timezone
import os
import json
import shutil
from pathlib import Path

# --- CONFIG ---
running_day = "sunday"  # options: saturday, sunday, monday
KEEP_DAYS = 7
HEADLESS = True
TIMEOUT_MS = 1000  # small wait between interactions

# --- PLACE MAP ---
PLACE_MAP = {
    "札幌": "SAPPORO",
    "函館": "HAKODATE",
    "福島": "FUKUSHIMA",
    "新潟": "NIIGATA",
    "東京": "TOKYO",
    "中山": "NAKAYAMA",
    "中京": "CHUKYO",
    "京都": "KYOTO",
    "阪神": "HANSHIN",
    "小倉": "KOKURA",
}

# --- DATE & FOLDER SETUP ---
JST = timezone(timedelta(hours=9))
today_jst = datetime.now(JST).strftime("%Y-%m-%d")
# --- Define project root and data folder ---
BASE_DIR = Path(__file__).resolve().parent.parent  # jradata/
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

data_dir = DATA_DIR / today_jst
data_dir.mkdir(exist_ok=True)


# --- DATE ---
today_jst = datetime.now(JST)
weekday = today_jst.weekday()  # Monday=0 ... Sunday=6

# --- MASTER INFO ---
master_info = {}

# --- SCRAPE ONE RACE ---
def scrape_one_race(page):
    page.locator("text='単勝・複勝'").first.click()
    page.wait_for_timeout(TIMEOUT_MS)
    page.locator("text='馬番順'").first.click()
    page.wait_for_timeout(TIMEOUT_MS)

    # --- TANSHO ---
    table = page.locator("table.basic.narrow-xy.tanpuku").first
    tbody = table.locator("tbody").first
    horse_number = tbody.locator("tr").count()
    tan_data = []

    for i in range(horse_number):
        row = tbody.locator("tr").nth(i)
        odds_cell = row.locator("td.odds_tan")
        tan_odds = odds_cell.inner_text().strip() if odds_cell.count() > 0 else ""
        tan_data.append([tan_odds])

    df_tan = pd.DataFrame({
        "NUM": range(1, horse_number + 1),
        "TANSHO": [row[0] for row in tan_data],
    })
    df_tan["TANSHO"] = pd.to_numeric(df_tan["TANSHO"], errors="coerce")
    df_tan = df_tan.sort_values(by="TANSHO", ascending=True).reset_index(drop=True)
    df_tan.index = df_tan.index + 1

    # --- FUKUSHO ---
    fuku_data = []
    for i in range(horse_number):
        row = tbody.locator("tr").nth(i)
        fuku_cell = row.locator("td.odds_fuku span.min")
        fuku_odds = fuku_cell.inner_text().strip() if fuku_cell.count() > 0 else ""
        fuku_data.append([fuku_odds])

    df_fuku = pd.DataFrame({
        "NUM": range(1, horse_number + 1),
        "FUKUSHO": [row[0] for row in fuku_data],
    })
    df_fuku["FUKUSHO"] = pd.to_numeric(df_fuku["FUKUSHO"], errors="coerce")
    df_fuku = df_fuku.sort_values(by="FUKUSHO", ascending=True).reset_index(drop=True)
    df_fuku.index = df_fuku.index + 1

    # --- UMAREN ---
    page.locator("text='馬連'").first.click()
    page.wait_for_timeout(TIMEOUT_MS)
    page.locator("text='人気順'").first.click()
    page.wait_for_timeout(TIMEOUT_MS)

    umaren_rows = []
    try:
        ul = page.locator("ul.umaren_list.pop.mt15").first
        li = ul.locator("li").first
        tbody = li.locator("tbody").first
        tr_first = tbody.locator("tr").nth(0)
        tr_second = tbody.locator("tr").nth(1)
        umaren_first = tr_first.locator("td.num").inner_text().strip()
        umaren_second = tr_second.locator("td.num").inner_text().strip()

        def extract_numbers(pair_text):
            return [int(x) for x in pair_text.split("-") if x.isdigit()]

        nums1 = extract_numbers(umaren_first)
        nums2 = extract_numbers(umaren_second)
        common_set = set(nums1) & set(nums2)
        common = str(list(common_set)[0]) if common_set else None
    except Exception:
        common = None

    if not common:
        print("⚠️ No common horses found — using fallback UMAREN.")
        df_umaren = pd.DataFrame({
            "UMAREN_NUM": range(1, horse_number + 1),
            "UMAREN_ODDS": [None] * horse_number,
        })
    else:
        page.locator("text='馬番順'").first.click()
        page.wait_for_timeout(TIMEOUT_MS)

        umaren_lists = page.locator("ul.umaren_list.mt15")
        ul_count = umaren_lists.count()
        found_common = False

        for ul_index in range(ul_count):
            ul = umaren_lists.nth(ul_index)
            li_count = ul.locator("li").count()
            for li_index in range(li_count):
                li = ul.locator("li").nth(li_index)
                table = li.locator("table.basic.narrow-xy.umaren").first
                caption = table.locator("caption").inner_text().strip()
                tbody = table.locator("tbody")
                if caption != common and not found_common:
                    tr_count = tbody.locator("tr").count()
                    for tr_index in range(tr_count):
                        tr = tbody.locator("tr").nth(tr_index)
                        th_val = tr.locator("th").inner_text().strip()
                        if th_val == common:
                            td_val = tr.locator("td").inner_text().strip().replace(",", "")
                            try:
                                td_val = float(td_val)
                            except:
                                td_val = None
                            umaren_rows.append([caption, td_val])
                            break
                elif caption == common:
                    found_common = True
                    umaren_rows.insert(0, [common, "N/A"])
                    tr_count = tbody.locator("tr").count()
                    for tr_index in range(tr_count):
                        tr = tbody.locator("tr").nth(tr_index)
                        th_val = tr.locator("th").inner_text().strip()
                        td_val = tr.locator("td").inner_text().strip().replace(",", "")
                        try:
                            td_val = float(td_val)
                        except:
                            td_val = None
                        umaren_rows.append([th_val, td_val])
                    break
            if found_common:
                break

        if not umaren_rows:
            umaren_rows = [[i + 1, None] for i in range(horse_number)]

        if umaren_rows and not any(str(row[0]) == common and str(row[1]) == "N/A" for row in umaren_rows):
            umaren_rows.insert(0, [common, "N/A"])

        first_row = umaren_rows[0]
        rest_rows = umaren_rows[1:]
        df_rest = pd.DataFrame(rest_rows, columns=["NUM", "ODDS"])
        df_rest["ODDS"] = pd.to_numeric(df_rest["ODDS"], errors="coerce")
        df_rest_sorted = df_rest.sort_values(by="ODDS", ascending=True).reset_index(drop=True)
        umaren_rows_sorted = [first_row] + df_rest_sorted.values.tolist()

        df_umaren = pd.DataFrame(umaren_rows_sorted, columns=["UMAREN_NUM", "UMAREN_ODDS"])

    
    # --- PAD & COMBINE (with error handling) ---
    max_len = max(len(df_umaren), len(df_tan), len(df_fuku))

    def pad_df(df, target_len, fill_value=""):
        if df is None or df.empty:
            return pd.DataFrame()  # Return empty DataFrame if input is invalid
        
        df = df.reset_index(drop=True)  # reset to 0-based index
        if len(df) < target_len:
            pad = pd.DataFrame(
                [[fill_value] * len(df.columns)] * (target_len - len(df)),
                columns=df.columns,
            )
            df = pd.concat([df, pad], ignore_index=True)
        return df

    # Apply padding to each DataFrame
    df_umaren = pad_df(df_umaren, max_len)
    df_tan = pad_df(df_tan, max_len)
    df_fuku = pad_df(df_fuku, max_len)

    # Combine with error checking
    if all(not df.empty for df in [df_umaren, df_tan, df_fuku]):
        combined_df = pd.concat([df_umaren, df_tan, df_fuku], axis=1, ignore_index=False)
    else:
        print("⚠️ Warning: One or more DataFrames were empty")
        combined_df = pd.DataFrame()  # Return empty DataFrame if any input was invalid

    return combined_df


# --- MAIN SCRIPT ---
with sync_playwright() as p:
    browser = p.chromium.launch(headless=HEADLESS)
    try:
        page = browser.new_page()
        page.goto("https://www.jra.go.jp")
        page.wait_for_timeout(TIMEOUT_MS)
        odds_buttons = page.locator("text='オッズ'")
        if odds_buttons.count() == 0:
            print("❌ No 'オッズ' link found — JRA site structure may have changed.")
            browser.close()
            exit(1)
        odds_buttons.nth(1).click()
        page.wait_for_timeout(TIMEOUT_MS)
        race_links = page.locator(("#contentsBody .content a[onclick^='return doAction']"))
        if race_links.count() == 0:
            print("🛑 No races available today. Exiting gracefully.")
            browser.close()
            exit(0)
        race_links.nth(0).click()
        page.wait_for_timeout(TIMEOUT_MS)
        page.locator("#contentsBody .tanpuku a[onclick^='return doAction']").nth(0).click()
        page.wait_for_timeout(TIMEOUT_MS)

        sections = page.locator("div.link_list.multi.div3.center.mid.narrow")
        count = sections.count()
        
        if count == 0:
            print("❌ No race sections found — probably no races today.")
            exit(0)

        if weekday not in (5, 6, 0):  # not Sat/Sun/Mon
            print("📅 Midweek detected — using previous weekend's date for folder naming.")
            # Go back to most recent Sunday (or Saturday if closer)
            days_since_sunday = (weekday - 6) % 7
            target_date = today_jst - timedelta(days=days_since_sunday)

        if count == 1:
            running_day = "saturday"  # rare single-day case
            target_index = 0
        elif count == 2:
            # Normal weekend (Saturday/Sunday)
            running_day = "saturday" if weekday == 5 else "sunday"
            target_index = 0 if running_day == "saturday" else 1
        elif count == 3:
            # 三連休 (Fri–Sun or Sat–Mon)
            if weekday == 4:
                running_day = "friday"
                target_index = 0
            elif weekday == 5:
                running_day = "saturday"
                target_index = 1 if "金曜" in sections.nth(0).inner_text() else 0
            elif weekday == 6:
                running_day = "sunday"
                target_index = 2 if "月曜" in sections.nth(2).inner_text() else 1
            elif weekday == 0:
                running_day = "monday"
                target_index = 2
            else:
                running_day = "sunday"
                target_index = 1
        else:
            raise ValueError(f"Unexpected sections count: {count}")

        print(f"🗓️  Detected {count} sections — running_day={running_day}, target_index={target_index}")

        # Select the correct section
        target_section = sections.nth(target_index)
        buttons = target_section.locator("a")
        num_places = buttons.count()

        for place_index in range(num_places):
            place_button = buttons.nth(place_index)
            place_name_jp = place_button.inner_text().strip()
            place_name = next((eng for jp, eng in PLACE_MAP.items() if jp in place_name_jp), None)
            if not place_name:
                print(f"Unknown place {place_name_jp}, skipping.")
                continue

            with page.expect_navigation():
                place_button.click()
            page.wait_for_timeout(TIMEOUT_MS)

            race_ul = page.locator("ul.nav.race-num.mt15").first
            race_count = race_ul.locator("li").count()

            for race_index in range(race_count):
                race_li = race_ul.locator("li").nth(race_index)
                race_button = race_li.locator("a")
                race_number = f"{race_index + 1}R"

                with page.expect_navigation():
                    race_button.click()
                page.wait_for_timeout(TIMEOUT_MS)

                combined_df = scrape_one_race(page)
                file_base = f"{place_name}_{race_number}"
                xlsx_path = data_dir / f"{file_base}.xlsx"
                json_path = data_dir / f"{file_base}.json"

                combined_df.to_excel(xlsx_path, index=False, header=False)
                combined_df.to_json(json_path, orient="values", force_ascii=False, indent=2)
                print(f"✅ Saved {file_base}")

                master_info.setdefault(place_name, {"jp_name": place_name_jp, "races": []})
                master_info[place_name]["races"].append(race_number)

                page.go_back()
                page.wait_for_timeout(TIMEOUT_MS)

            page.go_back()
            page.wait_for_timeout(TIMEOUT_MS)

        master_path = data_dir / "master.json"
        master_data = {
            "date": today_jst.strftime("%Y-%m-%d"),
            "places": [
                {"name": k, "jp_name": v["jp_name"], "races": v["races"]}
                for k, v in master_info.items()
            ],
            "last_updated": datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S"),
        }
        master_path.write_text(json.dumps(master_data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"🗂️ Saved master.json with {len(master_info)} places.")

        # --- CLEAN OLD FOLDERS ---
        all_dirs = sorted(
            [d for d in Path("data").iterdir() if d.is_dir() and d.name.startswith("20")],
            key=lambda x: x.name,
            reverse=True,
        )
        for d in all_dirs[KEEP_DAYS:]:
            try:
                shutil.rmtree(d)
                print(f"🧹 Deleted old data folder: {d.name}")
            except Exception as e:
                print(f"⚠️ Failed to delete {d.name}: {e}")

    finally:
        browser.close()
