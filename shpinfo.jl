#!/usr/local/bin/julia
using Shapefile
using DataFrames

global nlogo_prjcs = ["Albers_Conic_Equal_Area", "Lambert_Conformal_Conic_2SP",
            "Polyconic", "Lambert_Azimuthal_Equal_Area", "Mercator_1SP",
            "Robinson", "Azimuthal_Equidistant", "Miller", "Stereographic",
            "Cylindrical_Equal_Area", "Oblique_Mercator", "Transverse_Mercator",
            "Equidistant_Conic", "hotine_oblique_mercator", "Gnomonic",
            "Orthographic"]

function shapeinfo(filename, n_values = 20)
    table = Shapefile.Table(filename)
    df = DataFrame(table)
    nr = length(table)
    tt = eltype(df[!, 1])
    tstr = "unknown geometry"
    if Shapefile.Point <: tt
        tstr = "points"
    elseif Shapefile.PointZ <: tt
        tstr = "3D points"
    elseif Shapefile.Polyline <: tt
        tstr = "lines"
    elseif Shapefile.PolylineZ <: tt
        tstr = "3D lines"
    elseif Shapefile.Polygon <: tt
        tstr = "polygons"
    elseif Shapefile.PolygonZ <: tt
        tstr = "3D polygons"
    end
    props = propertynames(table)
    nc = length(props)
    prjfile = replace(filename, ".shp" => ".prj")
    prj = "unknown[]"
    if isfile(prjfile)
        prj = String(read(prjfile))
    end
    nlogo = false
    prjname = prj[1:(findfirst("[", prj)[1] - 1)]
    q1 = findfirst("\"", prj)[1] + 1
    q2 = findfirst("\"", prj[q1:length(prj)])[1]
    prjlabel = prj[q1:q2]
    if prjname == "GEOGCS"
        nlogo = true
    elseif prjname == "PROJCS"
        for projstr in nlogo_prjcs
            if startswith(prj, "PROJCS[\"$projstr\"")
                nlogo = true
            end
        end
        prjname = "PROJCS($prjlabel)"
    end
    supported = nlogo ? "supported" : "unsupported"

    println("\t$tstr in $supported projection $prjname with $nc properties and $nr rows")
    for prop in sort(props)
        if String(prop) != "geometry"
            pt = eltype(df[!, prop])
            d = Dict{pt, Int}()
            na = 0
            nascii = 0
            for entry in df[!, prop]
                if ismissing(entry)
                    na += 1
                else
                    if haskey(d, entry)
                        d[entry] = d[entry] + 1
                    else
                        d[entry] = 1
                        if isa(entry, String) && !isascii(entry)
                            nascii += 1
                        end
                    end
                end
            end
            nv = length(d)
            if nv <= n_values
                vv = join(sort([i for i in keys(d)]), ", ")
                println("\t\t$prop ($pt) in {$vv} with $na missing and $nascii not ASCII")
            else
                println("\t\t$prop ($pt) with $nv different values and $na missing and $nascii not ASCII")
            end
        end
    end
    println()
end

global default_dirs = [ "." ]
global n_values = 20

global args = copy(ARGS)
while length(args) > 0 && startswith(args[1], "-")
    opt = popfirst!(args)
    if opt == "--values" || opt == "-v"
        global n_values = parse(Int, popfirst!(args))
    elseif opt == "--help" || opt == "-h"
        println("Usage: $PROGRAM_FILE [--values <n. feature values to show per feature>] {dirs...}")
        println("\tIf dirs not given, cwd is the default")
        exit(0)
    else
        println("Unrecognized option $opt, try $PROGRAM_FILE --help")
        exit(1)
    end
end

if length(args) == 0
    args = copy(default_dirs)
end

for arg in args
    if isdir(arg)
        for (root, dirs, files) in walkdir(arg)
            for file in files
                if endswith(file, ".shp")
                    println(repeat("-", 79))
                    println("Found shapefile $file in directory $root")
                    shapeinfo(joinpath(root, file))
                end
            end
        end
    else
        if endswith(arg, ".shp") && isfile(arg)
            println(repeat("-", 79))
            println("Found shapefile $arg")
            shapeinfo(arg)
        else
            println(stderr, "$arg is not a shapefile")
        end
    end
end
