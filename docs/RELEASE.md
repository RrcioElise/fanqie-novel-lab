# Release Guide

## 版本号

项目使用 `pyproject.toml` 中的 `version` 字段作为 Python 包版本。建议采用语义化版本：

- `0.1.x`：早期预览和修复
- `0.2.x`：新增稳定功能
- `1.0.0`：工作流和 API 相对稳定

## 发布前检查

macOS / Linux:

```bash
python -m py_compile $(find src -name '*.py')
python -m unittest discover -s tests
fanqie-lab open-source-check
```

Windows:

```powershell
python -c "import pathlib, py_compile; [py_compile.compile(str(p), doraise=True) for p in pathlib.Path('src').rglob('*.py')]"
python -m unittest discover -s tests
fanqie-lab open-source-check
```

## 打 tag

```bash
git tag v0.1.0
git push origin v0.1.0
```

## GitHub Release 内容建议

- Highlights：新增能力
- Fixed：修复问题
- Changed：破坏性变更或配置变化
- Upgrade notes：升级注意事项
- Known issues：已知问题
