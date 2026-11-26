#!/usr/bin/env bash
set -e
for y in 2022 2023 2024 2025 2026 2027; do dotnet build Addin -c Release -p:RevitYear=$y; done
