import os
import json
import shutil
from pathlib import Path

SRC_DIR = Path("src_data")
DIST_INDIVIDUAL = Path("data/individual")
DIST_FAMILY = Path("data/family")

# 古い出力フォルダをきれいに掃除
if DIST_INDIVIDUAL.exists():
    shutil.rmtree(DIST_INDIVIDUAL)
if DIST_FAMILY.exists():
    shutil.rmtree(DIST_FAMILY)

DIST_INDIVIDUAL.mkdir(parents=True, exist_ok=True)
DIST_FAMILY.mkdir(parents=True, exist_ok=True)

# 28種類の型番ルール
CATEGORY_RULES = {
    "character": ["CH-", "CPC-", "SPC-"],
    "monster":   ["1F", "2E", "3D", "4C", "5B", "6A", "7S", "8SS", "9X", "CPM-", "SPM-"],
    "weapon":    ["1W", "CP-1W", "SP-1W"],
    "armor":     ["2D", "CP-2D", "SP-2D"],
    "accessory": ["3A", "CP-3A", "SP-3A"],
    "skill":     ["SK-", "SL-", "PS-"],
    "item":      ["AF-", "BC-", "IT-", "KE-", "MT-"],
    "interior":  ["FU-", "CPF-", "SPF-"]
}

def detect_category_by_id(data_id):
    data_id_str = str(data_id).strip()
    for prefix in ["1F", "2E", "3D", "4C", "5B", "6A", "7S", "8SS", "9X", "1W", "2D", "3A"]:
        if data_id_str.upper().startswith(prefix):
            if prefix == "1W": return "weapon"
            if prefix == "2D": return "armor"
            if prefix == "3A": return "accessory"
            return "monster"
    for cat_name, prefixes in CATEGORY_RULES.items():
        for prefix in prefixes:
            if data_id_str.upper().startswith(prefix.upper()):
                return cat_name
    return "unknown"

def main():
    pools = {
        "character": [], "monster": [], "weapon": [], "armor": [],
        "accessory": [], "skill": [], "item": [], "interior": []
    }
    mame_db = {}
    
    # 🗃️ すべての作品データをIDごとに溜め込む大きな引き出し
    all_combined_data = {}

    # src_data フォルダの中をスキャン
    for file_path in SRC_DIR.glob("*.json"):
        filename = file_path.name
        
        if "mamechishiki" in filename:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    for m in data:
                        if isinstance(m, dict) and "id" in m:
                            mame_db[str(m["id"])] = m
                elif isinstance(data, dict):
                    mame_db.update(data)
            continue

        with open(file_path, "r", encoding="utf-8") as f:
            try:
                data_list = json.load(f)
            except json.JSONDecodeError:
                continue
                
            if not isinstance(data_list, list):
                continue

            for item in data_list:
                if not isinstance(item, dict):
                    continue
                
                my_id = str(item.get("id", "")).strip()
                if not my_id:
                    continue

                # 型番ルールに従って「名簿上のID」を自動補正
                if "dish" in filename.lower():
                    cat = "item"
                else:
                    cat = detect_category_by_id(my_id)
                
                final_id = my_id if cat == "monster" or cat == "unknown" else f"{cat[:2]}_{my_id}"

                # 🤝 【同じIDの箱に入れるだけのシンプルな合体ルール】
                if final_id not in all_combined_data:
                    all_combined_data[final_id] = {}
                
                all_combined_data[final_id].update(item)
                all_combined_data[final_id]["id"] = final_id

                # 作品別データ以外の純粋なマスタ（monster.jsonなど）を判別して一覧に登録
                is_specific = any(x in filename.lower() for x in ["dqsg", "walk", "tact", "dqmsl", "details"])
                if not is_specific and cat != "unknown":
                    if all_combined_data[final_id] not in pools[cat]:
                        pools[cat].append(all_combined_data[final_id])

    # 図図鑑番号と矢印移動リンクの自動計算
    for cat_name, data_list in pools.items():
        process_zukan_and_links(data_list, prefix="No.")

    # まめちしき、色違い、シリーズ、お友達リンク自動結合
    for my_id, item in all_combined_data.items():
        pure_id = my_id.split("_") if "_" in my_id else my_id
        
        if pure_id in mame_db:
            item["mamechishiki_pages"] = [mame_db[pure_id]]
        elif my_id in mame_db:
            item["mamechishiki_pages"] = [mame_db[my_id]]

        if "monster_family" in item and item["monster_family"]:
            family = item["monster_family"]
            item["color_variants"] = [
                {"id": m["id"], "name": m.get("name") or m.get("dqsg_name", ""), "image_url": m.get("image_url") or m.get("dqsg_image_url", ""), "page_url": str(m.get("page_url", ""))}
                for m in pools["monster"] if m.get("monster_family") == family and m["id"] != my_id
            ]

    # 💾 個別JSONファイルの書き出し（同じIDのデータがすべて1つに大合体した状態！）
    for my_id, item in all_combined_data.items():
        file_name = f"{my_id}.json"
        with open(DIST_INDIVIDUAL / file_name, "w", encoding="utf-8") as f:
            json.dump(item, f, ensure_ascii=False, indent=2)

    # 🅱️ 系統別JSON（モンスター一覧用）の出力
    family_groups = {}
    for m in pools["monster"]:
        fam = m.get("main_family", "その他")
        if fam not in family_groups:
            family_groups[fam] = []
        
        # 👑 【完全自動】大元の「name」を守り、無ければ40作品のどれかの「_name」を自動スキャン
        display_name = m.get("name") or next((v for k, v in m.items() if k.endswith("_name")), "")
        
        # 🖼️ 【完全自動】大元の「image_url」を探し、無ければ40作品のどれかの「_image_url」を自動スキャン
        display_image = m.get("image_url") or next((v for k, v in m.items() if k.endswith("image_url")), "")

        family_groups[fam].append({
            "id":               m["id"],
            "name":             display_name,
            "furigana":         m.get("furigana") or m.get("dqsg_furigana", ""),
            "page_url":         str(m.get("page_url", "")),
            "image_url":        display_image,
            "search_keywords":  m.get("search_keywords", []),
            "first_appearance": m.get("first_appearance", ""),
            "appearances":      m.get("appearances", []),
            "main_family":      m.get("main_family", ""),
            "sub_family":       m.get("sub_family", ""),
            "release_date":     m.get("release_date") or m.get("dqsg_release_date", ""),
            "zukan_no":         m.get("zukan_no", "No.-----")
        })

    for fam_name, m_list in family_groups.items():
        m_list.sort(key=lambda x: str(x["id"]))
        with open(DIST_FAMILY / f"{fam_name}.json", "w", encoding="utf-8") as f:
            json.dump(m_list, f, ensure_ascii=False, indent=2)

    print("✨ すべてのデータを上書きせず、同じIDの箱に完璧にドッキングしたよ！ ✨")

def process_zukan_and_links(data_list, prefix="No."):
    if not data_list:
        return
    data_list.sort(key=lambda x: str(x["id"]).upper())
    for i, item in enumerate(data_list):
        item["zukan_no"] = f"{prefix}{str(i + 1).zfill(5)}"
        item["page_url"] = str(item.get("page_url", "")).strip()
    valid_items = [m for m in data_list if m["page_url"] != ""]
    for item in data_list:
        item["prev_id"] = ""
        item["prev_page_url"] = ""
        item["next_id"] = ""
        item["next_page_url"] = ""
        if item["page_url"] == "":
            continue
        try:
            valid_index = valid_items.index(item)
        except ValueError:
            continue
        if valid_index > 0:
            prev_m = valid_items[valid_index - 1]
            item["prev_id"] = prev_m["id"]
            item["prev_page_url"] = prev_m["page_url"]
        if valid_index < len(valid_items) - 1:
            next_m = valid_items[valid_index + 1]
            item["next_id"] = next_m["id"]
            item["next_page_url"] = next_m["page_url"]

if __name__ == "__main__":
    main()
