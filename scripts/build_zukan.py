import os
import json
import shutil  # 💡 フォルダを丸ごと掃除するために追加
from pathlib import Path

SRC_DIR = Path("src_data")
DIST_INDIVIDUAL = Path("data/individual")
DIST_FAMILY = Path("data/family")

# 🚨【全自動クリーンアップ機能】
# すでにフォルダが存在する場合は、中身（古い小文字ファイルなど）をごっそり削除します！
if DIST_INDIVIDUAL.exists():
    shutil.rmtree(DIST_INDIVIDUAL)
if DIST_FAMILY.exists():
    shutil.rmtree(DIST_FAMILY)

# まっさらな状態でフォルダを再作成します
DIST_INDIVIDUAL.mkdir(parents=True, exist_ok=True)
DIST_FAMILY.mkdir(parents=True, exist_ok=True)

def load_json(filename):
    path = SRC_DIR / filename
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def main():
    characters = load_json("character.json")
    monsters = load_json("monster.json")
    skills = load_json("skill.json")
    weapons = load_json("weapon.json")
    armors = load_json("armor.json")
    accessories = load_json("accessory.json")
    dishes = load_json("dish.json")
    items = load_json("item.json")
    interiors = load_json("interior.json")
    mamechishiki = load_json("mamechishiki.json")

    print(f"🔍 読み込み直後のモンスター数: {len(monsters)} 件")

    # 💡 全モンスターを大文字のID順で綺麗に整列！
    monsters.sort(key=lambda x: x["id"].upper())

    # 🔢 まずは全員に図鑑番号を割り振り、page_urlを文字列型に統一
    for i, item in enumerate(monsters):
        item["zukan_no"] = f"No.{str(i + 1).zfill(5)}"
        item["page_url"] = str(item.get("page_url", "")).strip()

    # 🔄 ページが存在する（URLが空ではない）モンスターだけのリストを作成
    valid_monsters = [m for m in monsters if m["page_url"] != ""]

    # 🔢 有効なモンスター同士で「前後のリンク」を計算して仕込む！
    for i, item in enumerate(monsters):
        item["prev_id"] = ""
        item["prev_page_url"] = ""
        item["next_id"] = ""
        item["next_page_url"] = ""

        if item["page_url"] == "":
            continue

        try:
            valid_index = valid_monsters.index(item)
        except ValueError:
            continue

        if valid_index > 0:
            prev_m = valid_monsters[valid_index - 1]
            item["prev_id"] = prev_m["id"]
            item["prev_page_url"] = prev_m["page_url"]

        if valid_index < len(valid_monsters) - 1:
            next_m = valid_monsters[valid_index + 1]
            item["next_id"] = next_m["id"]
            item["next_page_url"] = next_m["page_url"]

    # すべてのモンスターへの前後リンク・スキップ付与が終わってから全データを合体！
    all_data = characters + monsters + skills + weapons + armors + accessories + dishes + items + interiors
    
    # 最新の名簿（db）を作成
    db = {item["id"]: item for item in all_data}
    print(f"🔍 名簿（db）に登録されたデータ総数: {len(db)} 件")

    # まめちしき（リスト型）を辞書型に変換
    mame_db = {}
    if isinstance(mamechishiki, list):
        mame_db = {m["id"]: m for m in mamechishiki if isinstance(m, dict) and "id" in m}
    elif isinstance(mamechishiki, dict):
        mame_db = mamechishiki

    # 🤝 ルール③：お友達リンク（色違い・シリーズ・関連データ・まめちしき）の合体
    for item in all_data:
        my_id = item["id"]
        
        # 📘 まめちしきの合体
        item["mamechishiki_pages"] = []
        if my_id in mame_db:
            item["mamechishiki_pages"].append(mame_db[my_id])

        # 🦎 モンスターの色違い（〜族）のまとめ
        if "monster_family" in item and item["monster_family"]:
            family = item["monster_family"]
            item["color_variants"] = [
                {"id": m["id"], "name": m["name"], "image_url": m.get("image_url", ""), "page_url": str(m.get("page_url", ""))}
                for m in monsters if m.get("monster_family") == family and m["id"] != my_id
            ]

        # ⚔️ 装備シリーズのまとめ
        my_weapon_series = item.get("weapon_series")
        my_armor_series = item.get("armor_series")
        my_access_series = item.get("accessory_series")
        
        current_series = my_weapon_series or my_armor_series or my_access_series
        if current_series:
            series_items = []
            for eq in (weapons + armors + accessories):
                if eq["id"] != my_id and (eq.get("weapon_series") == current_series or eq.get("armor_series") == current_series or eq.get("accessory_series") == current_series):
                    series_items.append({"id": eq["id"], "name": eq["name"], "image_url": eq.get("image_url", ""), "page_url": str(eq.get("page_url", ""))})
            item["series_equipments"] = series_items

        # 🪑 家具シリーズのまとめ
        if "interior_series" in item and item["interior_series"]:
            int_series = item["interior_series"]
            item["interior_series_items"] = [
                {"id": f["id"], "name": f["name"], "image_url": f.get("image_url", ""), "page_url": str(f.get("page_url", ""))}
                for f in interiors if f.get("interior_series") == int_series and f["id"] != my_id
            ]

        # ⛓️ 関連データ自動合体
        for rel_key in ["related_characters", "related_items", "related_skill"]:
            if rel_key in item:
                detailed_list = []
                for rel_id in item[rel_key]:
                    if rel_id in db:
                        target = db[rel_id]
                        
                        detailed_data = {
                            "id": rel_id,
                            "name": target["name"],
                            "page_url": str(target.get("page_url", "")),
                            "image_url": target.get("image_url", "")
                        }
                        
                        if "prev_page_url" in target:
                            detailed_data["prev_id"] = target.get("prev_id", "")
                            detailed_data["prev_page_url"] = target.get("prev_page_url", "")
                            detailed_data["next_id"] = target.get("next_id", "")
                            detailed_data["next_page_url"] = target.get("next_page_url", "")
                            detailed_data["zukan_no"] = target.get("zukan_no", "")
                        
                        detailed_list.append(detailed_data)
                item[f"{rel_key}_details"] = detailed_list

    # 💾 4. ファイルを書き出すよ！
    
    # 🅰️ パターンA：IDごとの完全バラバラ個別JSON
    for item in all_data:
        # 大文字を維持したファイル名で保存
        file_name = f"{item['id']}.json"
        with open(DIST_INDIVIDUAL / file_name, "w", encoding="utf-8") as f:
            json.dump(item, f, ensure_ascii=False, indent=2)

    # 🅱️ 系統別のJSON（一覧ページ用）
    family_groups = {}
    for m in monsters:
        fam = m.get("main_family", "その他")
        if fam not in family_groups:
            family_groups[fam] = []
        
        latest_m = db.get(m["id"], m)
        
        family_groups[fam].append({
            "id": latest_m["id"],
            "name": latest_m["name"],
            "furigana": latest_m.get("furigana", ""),
            "page_url": str(latest_m.get("page_url", "")),
            "image_url": latest_m.get("image_url", ""),
            "search_keywords": latest_m.get("search_keywords", []),
            "first_appearance": latest_m.get("first_appearance", ""),
            "appearances": latest_m.get("appearances", []),
            "main_family": latest_m.get("main_family", ""),
            "sub_family": latest_m.get("sub_family", ""),
            "release_date": latest_m.get("release_date", ""),
            "zukan_no": latest_m.get("zukan_no", "No.-----")
        })

    for fam_name, m_list in family_groups.items():
        m_list.sort(key=lambda x: x["id"])
        with open(DIST_FAMILY / f"{fam_name}.json", "w", encoding="utf-8") as f:
            json.dump(m_list, f, ensure_ascii=False, indent=2)

    print("✨ 古いデータを自動消去して、新しいJSONの合体が完璧に終わったよ！ ✨")

if __name__ == "__main__":
    main()
