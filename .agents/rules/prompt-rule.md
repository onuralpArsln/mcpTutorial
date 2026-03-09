---
trigger: always_on
---

When a rule is being integrated in prompts it should be integrated by reading a yaml under knowledge folder
It  is allowed to have hard coded prompts like "considering this data {data from code}" or "answer by considering following:" such wording is allowed but the following rules must be pulled from yaml
it is important for reducing prompt size since we have limited input tokes.
Rules about db-> do not hard code get from yaml
rules about strategy -> do not hard code get them from yaml
etc