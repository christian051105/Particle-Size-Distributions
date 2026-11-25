PACKAGER=pyinstaller
SPEC=gsdfit.spec
SOURCE=$(shell python -c "import pathlib; print(*[str(p) for p in pathlib.Path('gsdfit').rglob('*') if p.suffix in ('.py', '.png')])")

.PHONY: build clean
build: dist/gsdfit

dist/gsdfit: $(SPEC) $(SOURCE)
	@if [ -d "dist/gsdfit" ]; then make clean; fi
	$(PACKAGER) $(SPEC)

.PHONY : clean
clean: 
	rm -r dist/gsdfit
