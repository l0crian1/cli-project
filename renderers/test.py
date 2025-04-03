#!/usr/bin/env python3

import sys
import json

if __name__ == "__main__":
    # Read and parse the configuration from stdin
    config = json.load(sys.stdin)
    print("\nTEST Configuration Received:")