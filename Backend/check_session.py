import asyncio, sys, warnings, json
warnings.filterwarnings('ignore')

async def check():
    from db.database import init_db, list_sessions, get_session
    await init_db()
    sessions = await list_sessions()
    if not sessions:
        print('No sessions found')
        return
    s = sessions[0]
    print(f'Latest session: {s.session_id}')
    print(f'Query: {s.query}')
    full = await get_session(s.session_id)
    print(f'Sources: {len(full.sources)}')
    print(f'Gaps: {len(full.gaps)}')
    print(f'Ideas: {len(full.ideas)}')
    print(f'Graph present: {full.knowledge_graph is not None}')
    if full.knowledge_graph:
        stats = full.knowledge_graph.get('statistics', {})
        print(f'Graph stats: {stats}')
        nodes = full.knowledge_graph.get('nodes', {})
        if nodes:
            first = list(nodes.values())[0]
            print(f'First node title: {first.get("title")}')
            print(f'First node keywords: {first.get("keywords", [])}')

asyncio.run(check())
