# Chat Statistics Display Implementation

## Overview

Successfully implemented detailed statistics display in the chat window, showing context used, token counts, source documents, and processing time for each AI response.

## Changes Made

### Backend Changes

#### [schemas.py](file:///Users/mk/Desktop/workspace/ai-stuff/langgraph/ai-app/backend/app/models/schemas.py)

Added new statistics models:

- **`SourceDocument`**: Metadata for source documents including filename, chunk info, and relevance score
- **`ResponseStatistics`**: Complete statistics model with tokens, context info, source documents, reasoning steps, and processing time

#### [graph_service.py](file:///Users/mk/Desktop/workspace/ai-stuff/langgraph/ai-app/backend/app/services/graph_service.py)

Updated `chat_stream()` method to track and return statistics:

- Track start time for processing duration calculation
- Collect source documents from RAG results with full metadata
- Count reasoning steps from multi-hop reasoning chain
- Estimate token counts (words × 1.3 approximation)
- Yield statistics as a dictionary event after response completion

Key statistics tracked:
- **Input tokens**: Estimated from prompt length
- **Output tokens**: Estimated from response length
- **Total tokens**: Sum of input and output
- **Source documents**: Full metadata including filename, chunk position, relevance score
- **Processing time**: Milliseconds from start to completion
- **Reasoning steps**: Count of multi-hop reasoning steps

#### [chat.py](file:///Users/mk/Desktop/workspace/ai-stuff/langgraph/ai-app/backend/app/routers/chat.py)

Updated `stream_generator()` to handle statistics events:

- Modified to handle dictionary items from `graph_service.chat_stream()`
- Emit `token` events for streaming text
- Emit `statistics` events with complete statistics data
- Both events use SSE format for real-time updates

---

### Frontend Changes

#### [useChat.ts](file:///Users/mk/Desktop/workspace/ai-stuff/langgraph/ai-app/frontend/src/hooks/useChat.ts)

Added statistics interfaces and handling:

- **`SourceDocument` interface**: Matches backend model
- **`MessageStatistics` interface**: Complete statistics structure
- Updated `Message` interface to include optional `statistics` field
- Added statistics event handler in SSE stream parser
- Statistics are attached to assistant messages when received

#### [MessageStatistics.tsx](file:///Users/mk/Desktop/workspace/ai-stuff/langgraph/ai-app/frontend/src/components/MessageStatistics.tsx)

Created new collapsible statistics component:

**Features:**
- Collapsible section (starts collapsed by default)
- Toggle button showing token count and processing time at a glance
- Expandable view with detailed sections:
  - **Tokens**: Input, output, and total with visual grid layout
  - **Context**: Number of documents used and reasoning steps
  - **Source Documents**: List with filename, chunk info, and relevance score
  - **Processing Time**: Response generation duration

**Styling:**
- Clean, minimal design matching existing UI
- Color-coded elements (blue highlights for important values)
- Responsive grid layout for token stats
- Document cards with left border accent
- Smooth transitions and hover effects

#### [MessageBubble.tsx](file:///Users/mk/Desktop/workspace/ai-stuff/langgraph/ai-app/frontend/src/components/MessageBubble.tsx)

Integrated statistics component:

- Import `MessageStatisticsComponent`
- Render statistics below assistant messages
- Only shown for assistant messages with statistics data

---

## Features

### Token Counting

Uses word-based approximation (words × 1.3) for token estimation:
- Fast and efficient
- Good enough for local models
- Can be replaced with `tiktoken` for OpenAI models if needed

### Source Document Display

Shows comprehensive metadata for each source:
- Document filename
- Chunk position (e.g., "Chunk 2 of 5")
- Relevance score (inverted distance, higher is better)
- Visual card layout with color coding

### Collapsible Design

Statistics start collapsed to avoid UI clutter:
- Toggle button shows key metrics at a glance
- Click to expand for full details
- Smooth animation

### Processing Time

Tracks end-to-end response generation:
- Measured in milliseconds
- Displayed in seconds with 2 decimal places
- Helps users understand performance

## Usage

The statistics are automatically displayed for all assistant responses. Users can:

1. **See summary**: Token count and processing time in collapsed view
2. **Expand details**: Click toggle to see full statistics
3. **View sources**: See which documents were used for RAG responses
4. **Track reasoning**: See how many reasoning steps were used

## Example Output

When RAG is enabled, users will see:

```
▶ 245 tokens • 1.23s

[Expanded view shows:]
TOKENS
Input: 180
Output: 65
Total: 245

CONTEXT
Documents Used: 3
Reasoning Steps: 0

SOURCE DOCUMENTS
📄 x-wp.pdf
Chunk 2 of 12
[Relevance: 0.85]

📄 h04556p1-virtualization-and-clustering-of-neeps-wp.pdf
Chunk 5 of 8
[Relevance: 0.78]

PROCESSING TIME
1.23s
```

## Benefits

1. **Transparency**: Users see exactly what context was used
2. **Performance insights**: Token counts and processing time visible
3. **Source tracking**: Easy to identify which documents contributed
4. **Debugging**: Helps identify when RAG is/isn't working
5. **Cost awareness**: Token counts help estimate API costs (for OpenAI models)
