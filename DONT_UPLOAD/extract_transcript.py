import json
import os

transcript_path = r'C:\Users\adarmawan117\.gemini\antigravity-ide\brain\9b12b645-a327-4200-b6da-e29157a90f79\.system_generated\logs\transcript.jsonl'
output_path = r'c:\Users\adarmawan117\Downloads\UndfxffAllW\RESULTS\python_test\DONT_UPLOAD\full_conversation_raw.txt'

try:
    with open(transcript_path, 'r', encoding='utf-8') as f_in, open(output_path, 'w', encoding='utf-8') as f_out:
        f_out.write("========================================================\n")
        f_out.write("FULL RAW CONVERSATION TRANSCRIPT\n")
        f_out.write("========================================================\n\n")
        
        for line in f_in:
            try:
                data = json.loads(line)
                step_type = data.get('type')
                source = data.get('source')
                
                # We only want to extract the back-and-forth chat, ignoring background tool calls/system messages unless they are responses.
                if step_type == 'USER_INPUT' and source == 'USER_EXPLICIT':
                    content = data.get('content', '')
                    f_out.write(f"\n[USER]:\n{content}\n")
                    f_out.write("-" * 50 + "\n")
                elif step_type == 'PLANNER_RESPONSE' and source == 'MODEL':
                    content = data.get('content', '')
                    if content: # Sometimes model output is just tool calls
                        f_out.write(f"\n[AI ARCHITECT]:\n{content}\n")
                        f_out.write("=" * 50 + "\n")
            except Exception as e:
                pass
    print("Extraction successful.")
except Exception as e:
    print(f"Error: {e}")
