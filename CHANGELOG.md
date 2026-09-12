# Changelog

## 1.0.2

- Expose the existing native menu-transition binding to module observers. Verify
  identifying context and uniqueness at initialization; retain the same menu
  switching call and native bridge.

## 1.0.1

- Keep menu-array initialization and diagnostic reads within their allocation. The extra sentinel is already included in the requested size; writing index `newSize` corrupted the heap when UI-dependent modules such as Automarket loaded.
- Reject invalid array growth sizes before copying entries.
