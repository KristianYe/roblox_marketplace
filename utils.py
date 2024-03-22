import time
from dataclasses import dataclass
from typing import List

import requests
from requests import JSONDecodeError, Response

from asset_types_map import asset_type_map

CATEGORIES = ("", 0, 1, 2, 3, 4, 5, 11, 12, 13)


@dataclass
class Item:
    id_: int = None
    name: str = None
    type: str = None
    restrictions: List[str] = None
    creator_name: str = None
    creator_id: int = None
    best_price: int = None
    tradable: bool = None
    holding_period: bool = None
    quantity_sold: int = None
    original_price: int = None
    average_price: int = None
    name_of_resellers: List[str] = None


def retry_on_timeout(seconds):
    def decorator(func):
        def wrapper(*args, **kwargs) -> dict | None:
            while True:
                response = func(*args, **kwargs)
                if response.status_code == 429:
                    print(
                        f"Timeout occurred. Retrying in {seconds} seconds..."
                    )
                    time.sleep(seconds)
                    continue
                elif response.status_code == 400:
                    return None
                else:
                    return response.json()

        return wrapper

    return decorator


@retry_on_timeout(5)  # seconds to wait before resending request
def get_json_from_api(url) -> Response:
    response = requests.get(url)

    return response


def collect_items() -> List[Item]:
    items = []

    for category in CATEGORIES:
        url = f"https://catalog.roblox.com/v2/search/items/details?Category={category}&SortAggregation=5&Limit=120"
        cursor = True
        while cursor:
            response = get_json_from_api(url)

            cursor = response.get("nextPageCursor")

            for item_info in response["data"]:
                items.append(collect_item_info(item_info))

            url = f"https://catalog.roblox.com/v2/search/items/" \
                  f"details?Category={category}&SortAggregation=5&Limit=120&Cursor={cursor}"

    return items


def collect_item_info(item_info: dict) -> Item:
    item = Item()
    collectible_item_id = item_info.get("collectibleItemId")
    has_resellers = item_info.get("hasResellers")
    item.id_ = item_info.get("id")
    item.name = item_info.get("name")
    item.restrictions = item_info.get("itemRestrictions")

    if item_info.get("itemType") == "Bundle":
        item.type = "Bundle"
    else:
        item.type = asset_type_map.get(item_info.get("assetType"))

    item.creator_name = item_info.get("creatorName")
    item.creator_id = item_info.get("creatorTargetId")
    item.tradable = any(
        restriction in ("Limited", "LimitedUnique")
        for restriction in item.restrictions
    )   # "tradable" depends on item's restrictions
    item.holding_period = any(
        restriction in ("Limited", "LimitedUnique", "Collectible")
        for restriction in item.restrictions
    )   # "holding_period" depends on item's restrictions
    item.original_price = item_info.get("price")
    item.best_price = item_info.get("lowestPrice")

    if "hasResellers" in item_info.keys():
        collect_resale_data(collectible_item_id, item)

    if collectible_item_id is not None and has_resellers is True:
        # temporary stub due to unexpected error
        try:
            item.name_of_resellers = collect_resellers(collectible_item_id)
        except JSONDecodeError:
            item.name_of_resellers = "error"

    return item


def collect_resellers(collectible_item_id: str) -> List[str]:
    url = f"https://apis.roblox.com/marketplace-sales/v1/item/{collectible_item_id}/resellers?limit=100"
    result = []
    resellers_info = []
    while True:
        response = get_json_from_api(url)
        resellers_info += response["data"]
        if not bool(response["nextPageCursor"]):
            break
        url = (
            f"https://apis.roblox.com/marketplace-sales/v1/item/{collectible_item_id}"
            f"/resellers?limit=100&cursor={response['nextPageCursor']}"
        )

    for reseller in resellers_info:
        result.append(reseller["seller"]["name"])

    return result


def collect_resale_data(collectible_item_id: str, item: Item):
    """
    Collects additional info from additional APIs
    Different items get data from different APIs
    :param collectible_item_id: string
    :param item: Item
    :return: None
    """
    url_1 = f"https://economy.roblox.com/v1/assets/{item.id_}/resale-data"
    url_for_avg_price = f"https://apis.roblox.com/marketplace-sales/v1/item/{collectible_item_id}/resale-data"
    url_for_sales = (
        "https://apis.roblox.com/marketplace-items/v1/items/details"
    )

    response = get_json_from_api(url_1)
    if response is None:    # if we did not find necessary data from first url, we are sending request to another
        response = requests.post(
            url_for_sales,
            json={
                "itemIds": [
                    collectible_item_id,
                ]
            },
        ).json()
        item.quantity_sold = response[0].get("sales")
        response = get_json_from_api(url_for_avg_price)
    else:
        item.quantity_sold = response["sales"]

    item.average_price = response["recentAveragePrice"]
