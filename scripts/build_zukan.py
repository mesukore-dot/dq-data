import os
import json
from pathlib import Path

# 📂 フォルダの場所を決めるよ
SRC_DIR = Path("src_data")      # 元の10個のJSONを置くフォルダ
DIST_INDIVIDUAL = Path("data/individual") # バラバラにした個別JSONの保存先
DIST_FAMILY = Path("data/family")         # 一覧ページ用の系統別JSONの保存先

# ディレクトリがなかったら自動で作るよ
DIST_INDIVIDUAL.mkdir(parents=True, exist_ok=True)
DIST_FAMILY.mkdir(parents=True, exist_ok=True)

def load_json(filename):
    path = SRC_DIR / filename
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def main():
    # 📥 1. 10個のファイルを全部読み込むよ！
    characters = load_json("character.json")
    monsters = load_json("monster.json")
    skills = load_json("skill.json")
    weapons = load_json("weapon.json")
    armors = load_json("armor.json")
    accessories = load_json("accessory.json")
    dishes = load_json("dish.json")
    items = load_json("item.json")
    interiors = load_json("interior.json")
    mamechishiki = load_json("mamechishiki.json")  # 辞書型を想定

    print(f"🔍 読み込み直後のモンスター数: {len(monsters)} 件")

    # すべてのデータを1つの巨大なリストにまとめる（まめちしき以外）
    all_data = characters + monsters + skills + weapons + armors + accessories + dishes + items + interiors
    
    # 🔍 検索しやすくするために、IDをキーにした辞書（名簿）を頭の中に作るよ
    db = {item["id"]: item for item in all_data}
    print(f"🔍 名簿（db）に登録されたデータ総数: {len(db)} 件")

    # --- 💡 ここから細かいルールの自動計算スタート！ ---

    # 🛑 ルール①：URL（page_url）があるものだけを集めて、図鑑のNo.を計算するよ
    valid_data = [item for item in all_data if item.get("page_url")]
    valid_data.sort(key=lambda x: x["id"]) # IDの昇順（小さい順）

    # 🔢 ルール②：No.の自動計算 ＆ 前後のIDと【実際のページURL】をセット
    for i, item in enumerate(valid_data):
        item["zukan_no"] = f"No.{str(i + 1).zfill(5)}"
        
        if i > 0:
            item["prev_id"] = valid_data[i - 1]["id"]
            # 💡 隣のモンスターの本物のURLをそのままコピーして持ってくるよ！
            item["prev_page_url"] = valid_data[i - 1].get("page_url", "")
        else:
            item["prev_id"] = ""
            item["prev_page_url"] = ""

        if i < len(valid_data) - 1:
            item["next_id"] = valid_data[i + 1]["id"]
            # 💡 隣のモンスターの本物のURLをそのままコピーして持ってくるよ！
            item["next_page_url"] = valid_data[i + 1].get("page_url", "")
        else:
            item["next_id"] = ""
            item["next_page_url"] = ""

    # 🤝 ルール③：お友達リンク（色違い・シリーズ・関連データ・まめちしき）の合体
    for item in all_data:
        # 💡 【エラー修正】ここで my_id を最初にカチッと定義するよ！
        my_id = item["id"]
        
        # 📘 まめちしきの合体（自分のIDと完全一致するものを1対1でくっつけるよ！）
        item["mamechishiki_pages"] = []
        if my_id in mamechishiki:
            item["mamechishiki_pages"].append(mamechishiki[my_id])

        # 🦎 モンスターの色違い（〜族）のまとめ
        if "monster_family" in item and item["monster_family"]:
            family = item["monster_family"]
            item["color_variants"] = [
                {"id": m["id"], "name": m["name"], "image_url": m.get("image_url", ""), "page_url": m.get("page_url", "")}
                for m in monsters if m.get("monster_family") == family and m["id"] != my_id
            ]

        # ⚔️ 装備シリーズのまとめ（武器・防具・アクセサリーをまたいで探すよ！）
        my_weapon_series = item.get("weapon_series")
        my_armor_series = item.get("armor_series")
        my_access_series = item.get("accessory_series")
        
        current_series = my_weapon_series or my_armor_series or my_access_series
        if current_series:
            series_items = []
            for eq in (weapons + armors + accessories):
                if eq["id"] != my_id and (eq.get("weapon_series") == current_series or eq.get("armor_series") == current_series or eq.get("accessory_series") == current_series):
                    series_items.append({"id": eq["id"], "name": eq["name"], "image_url": eq.get("image_url", ""), "page_url": eq.get("page_url", "")})
            item["series_equipments"] = series_items

        # 🪑 家具シリーズのまとめ（家具はインテリアの中だけで探す！）
        if "interior_series" in item and item["interior_series"]:
            int_series = item["interior_series"]
            item["interior_series_items"] = [
                {"id": f["id"], "name": f["name"], "image_url": f.get("image_url", ""), "page_url": f.get("page_url", "")}
                for f in interiors if f.get("interior_series") == int_series and f["id"] != my_id
            ]

        # ⛓️ 関連キャラ・関連アイテムの「画像とリンク」を自動で引っ張る
        for rel_key in ["related_characters", "related_items", "related_skill"]:
            if rel_key in item:
                detailed_list = []
                for rel_id in item[rel_key]:
                    if rel_id in db:
                        target = db[rel_id]
                        detailed_list.append({
                            "id": rel_id,
                            "name": target["name"],
                            "page_url": target.get("page_url", ""),
                            "image_url": target.get("image_url", "")
                        })
                item[f"{rel_key}_details"] = detailed_list

    # 💾 4. ファイルを書き出すよ！
    
    # 🅰️ パターンA：IDごとの完全バラバラ個別JSON（URL関係なく全員分強制で作るよ！）
    for item in all_data:
        file_name = f"{item['id']}.json".lower() # 💡大文字小文字トラブルを防ぐため小文字名で統一して保存
        with open(DIST_INDIVIDUAL / file_name, "w", encoding="utf-8") as f:
            json.dump(item, f, ensure_ascii=False, indent=2)

    # 🅱️ 系統別のJSON（一覧ページ用）
    family_groups = {}
    for m in monsters:
        if not m.get("page_url"):
            continue
            
        fam = m.get("main_family", "その他")
        if fam not in family_groups:
            family_groups[fam] = []
        
        family_groups[fam].append({
            "id": m["id"],
            "name": m["name"],
            "furigana": m.get("furigana", ""),
            "page_url": m.get("page_url", ""),
            "image_url": m.get("image_url", ""),
            "search_keywords": m.get("search_keywords", []),
            "first_appearance": m.get("first_appearance", ""),
            "appearances": m.get("appearances", []),
            "main_family": m.get("main_family", ""),
            "sub_family": m.get("sub_family", ""),
            "release_date": m.get("release_date", ""),
            "zukan_no": m.get("zukan_no", "No.-----")
        })

    for fam_name, m_list in family_groups.items():
        m_list.sort(key=lambda x: x["id"])
        with open(DIST_FAMILY / f"{fam_name}.json", "w", encoding="utf-8") as f:
            json.dump(m_list, f, ensure_ascii=False, indent=2)

    print("✨ すべてのJSONデータの仕分けと合体が完璧に終わったよ！ ✨")

if __name__ == "__main__":
    main()
