from tavily import *


def search_google(query: str) -> dict:
    """
    This tool will provide you the realtime data and information from the web. You just need to call this tool and pass the query parameter and then it will return a dict containing some information about the search.
    """
    tavily_client = TavilyClient(api_key="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")
    response = tavily_client.search(query=query)
    
    return response

print(search_google("epstien files!"))