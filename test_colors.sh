#!/bin/bash

# Test color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${RED}Red text${NC}"
echo -e "${GREEN}Green text${NC}"
echo -e "${YELLOW}Yellow text${NC}"
echo -e "${BLUE}Blue text${NC}"
echo "Normal text"