import os
import json
import shutil
from pathlib import Path

SRC_DIR = Path("src_data")
DIST_INDIVIDUAL = Path("data/individual")
DIST_FAMILY = Path("data/family")


# 🚨 【全自動クリーンアップ機能】
# 古い個別ファイルや系統別ファイルをまっさらに掃除します
if DIST_INDIVIDUAL.exists():
    shutil.rmtree(DIST_INDIVIDUAL)

if DIST_FAMILY.exists():
    shutil.rmtree(DIST_FAMILY)

DIST_INDIVIDUAL.mkdir(parents=True, exist_ok=True)
DIST_FAMILY.mkdir(parents=True, exist_ok=True)


# 📖 あなたがひたすら教えてくれた「28種類の型番ルール」
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
    """
    🔍 IDの頭文字から、それが何のカテゴリかを28ルールを元に自動判別する関数
    """
    data_id_str = str(data_id).strip()
    
    # 1. 特殊な2文字・3文字ルール（1F〜9X、1W、2D、3A、8SS）の先頭一致チェック
    for prefix in ["1F", "2E", "3D", "4C", "5B", "6A", "7S", "8SS", "9X", "1W", "2D", "3A"]:
        if data_id_str.upper().startswith(prefix):
            if prefix == "1W": 
                return "weapon"
            if prefix == "2D": 
                return "armor"
            if prefix == "3A": 
                return "accessory"
            return "monster"  # 1F〜9X、8SSはモンスター
            
    # 2. ハイフン付きのプレフィックス（CH-やCP-1Wなど）のチェック
    for cat_name, prefixes in CATEGORY_RULES.items():
        for prefix in prefixes:
            if data_id_str.upper().startswith(prefix.upper()):
                return cat_name
                
    return "unknown"


def get_safe_id_mapping(rel_id, db):
    """
    🛡️ 【全滅防止の安全装置】
    関連IDに古い純粋な型番が書かれていても、裏で自動補正して名簿(db)から安全に引っ張ってくる関数
    """
    rel_id_str = str(rel_id).strip()
    if rel_id_str in db:
        return rel_id_str
        
    # 人間が「ch_」などを付け忘れても、名簿側でカテゴリプレフィックスが付いていれば自動補完して探す
    cat = detect_category_by_id(rel_id_str)
    if cat != "unknown" and cat != "monster":
        possible_id = f"{cat[:2]}_{rel_id_str}"  # 例: ch_CH-1N01-001
        if possible_id in db:
            return possible_id
            
    return None  # 見つからない場合は安全に無視（エラーでActionsを止めない）


def process_zukan_and_links(data_list, prefix="No."):
    """
    📂 カテゴリごとに図鑑番号を振り、個別の矢印リンク(◀ ▶)を自動計算する関数
    """
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
def main():
    # 🌟 各カテゴリのプール（お部屋）を用意
    pools = {
        "character": [], 
        "monster":   [], 
        "weapon":    [], 
        "armor":     [],
        "accessory": [], 
        "skill":     [], 
        "item":      [], 
        "interior":  []
    }
    mame_db = {}
    
    # 🌟 スマグロ（DQSG）などの作品固有データを一時保存する辞書
    title_specific_data = {}

    # 🚀 【新機能】src_data フォルダの中を全自動でスキャン！
    for file_path in SRC_DIR.glob("*.json"):
        filename = file_path.name
        
        # まめちしきファイルの個別処理
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

        # 通常の作品データの読み込み
        with open(file_path, "r", encoding="utf-8") as f:
            try:
                data_list = json.load(f)
            except json.JSONDecodeError:
                print(f"⚠️ 警告: {filename} のJSON形式が正しくないためスキップします。")
                continue
                
            if not isinstance(data_list, list):
                continue

            # ファイル名から作品名（シリーズ名）を自動抽出 (例: DQSG_memory.json -> DQSG)
            title_id = filename.split("_")[0].replace(".json", "")

            # 1件ずつ中身をチェックして、28ルールに沿って自動で部屋に振り分ける
            for item in data_list:
                if not isinstance(item, dict):
                    continue
                
                # 💡 スマグロ用の「dqsg_id」がある場合はそれを優先、なければ通常の「id」を見る
                my_id = str(item.get("dqsg_id") or item.get("id", "")).strip()
                if not my_id:
                    continue
                    
                cat = detect_category_by_id(my_id)
                
                if cat != "unknown":
                    # モンスター以外はIDの重複を防ぐために、名簿上だけ頭文字（ch_やwp_）を自動付与
                    final_id = my_id if cat == "monster" else f"{cat[:2]}_{my_id}"
                    item["id"] = final_id
                    
                    # 💡 もし「dqsg_id」から始まる作品データだった場合、個別データとして後でドッキングするために退避
                    if "dqsg_id" in item:
                        if final_id not in title_specific_data:
                            title_specific_data[final_id] = {}
                        
                        # 画面側で使いやすいように「作品名_data」という引き出しを作る (例: dqsg_data)
                        title_specific_data[final_id][f"{title_id.lower()}_data"] = item
                        
                        # スマグロのメモリデータ自体はモンスターに統合されるため、メインのプール追加からは除外します
                        continue
                    
                    pools[cat].append(item)

    print(f"🔍 スキャン完了 - モンスター総数: {len(pools['monster'])} 件")

    # 🛠️ すべてのカテゴリで「図鑑No.」と「矢印リンク（◀ ▶）」を自動計算！
    for cat_name, data_list in pools.items():
        process_zukan_and_links(data_list, prefix="No.")

    # 🗃️ すべてのプールを合体させて、大元の安全な名簿（db）を作成
    all_data = []
    for data_list in pools.values():
        all_data.extend(data_list)
    db = {item["id"]: item for item in all_data}

    # 💡 【重要】プールから除外されていたスマグロ固有のデータを大元の名簿(db)にドッキング！
    for target_id, specific_content in title_specific_data.items():
        if target_id in db:
            db[target_id].update(specific_content)
        else:
            # 万が一ベースとなるモンスターデータ側にまだ登録されていないIDのメモリがあった場合も、救済します
            new_item = {"id": target_id}
            new_item.update(specific_content)
            for data_body in specific_content.values():
                if "name" in data_body:
                    new_item["name"] = data_body["name"]
                    break
            db[target_id] = new_item
            all_data.append(new_item)

    print(f"🔍 名簿（db）に登録されたデータ総数: {len(db)} 件")

    # ⛓️ お友達リンク（まめちしきや関連データの自動結合処理）
    for item in all_data:
        my_id = item["id"]
        pure_id = my_id.split("_")[1] if "_" in my_id else my_id
        
        # 📘 まめちしきの合体
        item["mamechishiki_pages"] = []
        if pure_id in mame_db:
            item["mamechishiki_pages"].append(mame_db[pure_id])
        elif my_id in mame_db:
            item["mamechishiki_pages"].append(mame_db[my_id])

        # 🦎 モンスターの色違いまとめ
        if "monster_family" in item and item["monster_family"]:
            family = item["monster_family"]
            item["color_variants"] = [
                {
                    "id":        m["id"], 
                    "name":      m["name"], 
                    "image_url": m.get("image_url", ""), 
                    "page_url":  str(m.get("page_url", ""))
                }
                for m in pools["monster"] if m.get("monster_family") == family and m["id"] != my_id
            ]

        # ⚔️ 装備シリーズのまとめ
        current_series = item.get("weapon_series") or item.get("armor_series") or item.get("accessory_series")
        if current_series:
            series_items = []
            for eq in (pools["weapon"] + pools["armor"] + pools["accessory"]):
                if eq["id"] != my_id and (eq.get("weapon_series") == current_series or eq.get("armor_series") == current_series or eq.get("accessory_series") == current_series):
                    series_items.append({
                        "id":        eq["id"], 
                        "name":      eq["name"], 
                        "image_url": eq.get("image_url", ""), 
                        "page_url":  str(eq.get("page_url", ""))
                    })
            item["series_equipments"] = series_items

        # 🗃️ 家具シリーズのまとめ
        if "interior_series" in item and item["interior_series"]:
            int_series = item["interior_series"]
            item["interior_series_items"] = [
                {
                    "id":        f["id"], 
                    "name":      f["name"], 
                    "image_url": f.get("image_url", ""), 
                    "page_url":  str(f.get("page_url", ""))
                }
                for f in pools["interior"] if f.get("interior_series") == int_series and f["id"] != my_id
            ]

        # ⛓️ 関連データの自動ドッキング（安全装置付き）
        for rel_key in ["related_characters", "related_items", "related_skill"]:
            if rel_key in item:
                detailed_list = []
                for rel_id in item[rel_key]:
                    safe_id = get_safe_id_mapping(rel_id, db)
                    if safe_id: 
                        target = db[safe_id]
                        detailed_data = {
                            "id":        target["id"],
                            "name":      target["name"],
                            "page_url":  str(target.get("page_url", "")),
                            "image_url": target.get("image_url", "")
                        }
                        if "prev_page_url" in target:
                            detailed_data["prev_id"]       = target.get("prev_id", "")
                            detailed_data["prev_page_url"] = target.get("prev_page_url", "")
                            detailed_data["next_id"]       = target.get("next_id", "")
                            detailed_data["next_page_url"] = target.get("next_page_url", "")
                            detailed_data["zukan_no"]      = target.get("zukan_no", "")
                        detailed_list.append(detailed_data)
                item[f"{rel_key}_details"] = detailed_list

    # 💾 4. ファイルの個別書き出し
    for item in all_data:
        file_name = f"{item['id']}.json"
        with open(DIST_INDIVIDUAL / file_name, "w", encoding="utf-8") as f:
            json.dump(item, f, ensure_ascii=False, indent=2)

    # 🅱️ 系統別のJSON（モンスター一覧ページ用）の出力
    family_groups = {}
    for m in pools["monster"]:
        fam = m.get("main_family", "その他")
        if fam not in family_groups:
            family_groups[fam] = []
        
        latest_m = db.get(m["id"], m)
        family_groups[fam].append({
            "id":               latest_m["id"],
            "name":             latest_m.get("name") or next((v for k, v in latest_m.items() if k.endswith("_name")), ""),
            "furigana":         latest_m.get("furigana", ""),
            "page_url":         str(latest_m.get("page_url", "")),
            "image_url":        latest_m.get("image_url", ""),
            "search_keywords":  latest_m.get("search_keywords", []),
            "first_appearance": latest_m.get("first_appearance", ""),
            "appearances":      latest_m.get("appearances", []),
            "main_family":      latest_m.get("main_family", ""),
            "sub_family":       latest_m.get("sub_family", ""),
            "release_date":     latest_m.get("release_date", ""),
            "zukan_no":         latest_m.get("zukan_no", "No.-----")
        })

    for fam_name, m_list in family_groups.items():
        m_list.sort(key=lambda x: str(x["id"]))
        with open(DIST_FAMILY / f"{fam_name}.json", "w", encoding="utf-8") as f:
            json.dump(m_list, f, ensure_ascii=False, indent=2)

    print("✨ すべての作品・カテゴリの自動スキャン、図鑑番号、矢印リンク合体が完璧に終わったよ！ ✨")


if __name__ == "__main__":
    main()
