#!/usr/bin/env python
"""Run the SahamApp API server with uvicorn."""

import uvicorn

if __name__ == '__main__':
    uvicorn.run('main:app', host='0.0.0.0', port=8767, reload=True)
