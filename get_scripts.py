import json

def get_scripts_to_run():
    with open('config.json', 'r') as f:
        config = json.load(f)
    
    scripts = []
    # Check each protocol section for configured items and a script field
    for protocol, protocol_config in config.get('protocols', {}).items():
        # If the protocol has any configuration and a script field, add it to the list
        if protocol_config and 'script' in protocol_config:
            scripts.append(protocol_config['script'])
    
    return scripts

if __name__ == '__main__':
    scripts = get_scripts_to_run()
    print("Scripts to run:", scripts) 