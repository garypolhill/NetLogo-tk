# nlogo2R.pm
#
# Perl library functions for converting Netlogo output to R

package nlogo2R;
require Exporter;

use strict;

our @ISA = qw(Exporter);
our @EXPORT = qw(setsep, getsep, readfile, nlogo2R, readturtles, readlinks);
our @EXPORT_OK = qw(readworld, readplots, readbspace, table2hash);
our $VERSION = v1.0;

my $dfsep = "\t";

sub setsep {
  $dfsep = $_[0];
}

sub getsep {
  return $dfsep;
}

sub readfile ($$;@) {
  my ($file, $metadata, @args) = @_;

  open(FILE, "<$file") or die "Cannot read netlogo output file $file: $!\n";

  my $line = <FILE>;

  if($line =~ /^\"export-plots/) {
    return readplots(*FILE, $file, $metadata);
  }
  elsif($line =~ /^\"export-world/) {
    return readworld(*FILE, $file, $metadata, @args);
  }
  elsif($line =~ /^\"BehaviorSpace/) {
    return readbspace(*FILE, $file, $metadata);
  }
  else {
    die "$file is not a recognised netlogo output file\n";
  }
}

sub readturtles ($) {
  my ($file) = @_;

  my ($headings, $data) = readfile($file, 0, 'turtles');

  my %turtles;

  foreach my $datum (@$data) {
    my $who;
    my %hash;
    for(my $i = 0; $i <= $#$headings; $i++) {
      if($$headings[$i] eq 'who') {
	$who = $$datum[$i];
      }
      $hash{$$headings[$i]} = $$datum[$i];
    }

    if(!defined($who)) {
      die "Cannot find 'who' in turtle data returned from reading world file",
      " $file\n";
    }

    $turtles{$who} = \%hash;
  }

  return \%turtles;
}

sub readlinks ($) {
  my ($file) = @_;

  my ($headings, $data) = readfile($file, 0, 'links');

  my %links;

  foreach my $datum (@$data) {
    my $end1;
    my $end2;
    my %hash;

    for(my $i = 0; $i <= $#$headings; $i++) {
      if($$headings[$i] eq 'end1') {
	$end1 = $$datum[$i];
      }
      elsif($$headings[$i] eq 'end2') {
	$end2 = $$datum[$i];
      }
      $hash{$$headings[$i]} = $$datum[$i];
    }

    if(!defined($end1) || !defined($end2)) {
      die "Cannot find both 'end1' and 'end2' in link data returned from ",
      "reading world file $file\n";
    }

    $end1 =~ s/\D//g;
    $end2 =~ s/\D//g;

    if(!defined($links{$end1})) {
      my %end2links;

      $end2links{$end2} = [\%hash];

      $links{$end1} = \%end2links;
    }
    elsif(!defined($links{$end1}->{$end2})) {
      $links{$end1}->{$end2} = [\%hash];
    }
    else {
      push(@{$links{$end1}->{$end2}}, \%hash);
    }
  }

  return \%links;
}

sub nlogo2R (\@$;$$@) {
  my ($Nfiles, $Rfile, $metadata, $sep, @args) = @_;

  $metadata = 0 if !defined($metadata);

  my $data;
  my $headers;

  for(my $i = 0; $i <= $#$Nfiles; $i++) {
    if($i == 0) {
      ($headers, $data) = readfile($$Nfiles[$i], $metadata, @args);
    }
    else {
      my ($headers1, $data1) = readfile($$Nfiles[$i], $metadata, @args);
      ($headers, $data) = merge($headers, $data, $headers1, $data1);
    }
  }

  saveR($data, $headers, $Rfile, $sep);
}

sub merge ($$$$) {
  my($h1, $d1, $h2, $d2) = @_;

  my %hh;

  my @headers;
  push(@headers, @$h1);

  for(my $i = 0; $i <= $#$h1; $i++) {
    $hh{$$h1[$i]} = [$i, -1];
  }

  for(my $i = 0; $i <= $#$h2; $i++) {
    if(defined($hh{$$h2[$i]})) {
      $hh{$$h2[$i]}->[1] = $i;
    }
    else {
      $hh{$$h2[$i]} = [-1, $i];
      push(@headers, $$h2[$i]);
    }
  }

  my @data;

  foreach my $loop ([$d1, 0], [$d2, 1]) {
    my ($d, $h) = @$loop;

    for(my $i = 0; $i <= $#$d; $i++) {
      my @rowdata;

      my $row = $$d[$i];

      for(my $j = 0; $j <= $#headers; $j++) {
	my $k = $hh{$headers[$j]}->[$h];

	$rowdata[$j] = ($k == -1) ? 'NA' : $$row[$k];
      }

      push(@data, \@rowdata);
    }
  }

  return (\@headers, \@data);
}

sub saveR ($$$;$) {
  my ($data, $headers, $Rfile, $sep) = @_;

  $sep = $dfsep if !defined($sep);

  open(R, ">$Rfile") or die "Cannot create R file $Rfile: $!\n";

  my @Rheaders = Rify(@$headers);

  print R join($sep, @Rheaders), "\n";

  for(my $i = 0; $i <= $#$data; $i++) {
    print R join($sep, @{$$data[$i]}), "\n";
  }

  close(R);
}

sub Rify (@) {
  my @headers = @_;

  my @Rheaders;

  for(my $i = 0; $i <= $#headers; $i++) {
    $Rheaders[$i] = $headers[$i];

    $Rheaders[$i] =~ s/\W/./g;

    $Rheaders[$i] =~ s/^(\d)/_$1/;
  }

  return @Rheaders;
}

sub readworld (*$$;@) {
  my ($fp, $file, $metadata, @args) = @_;

  my $netlogo = &readqline($fp);
  my $date = &readqline($fp);

  for(my $line = &readqline($fp);
      $line ne 'GLOBALS';
      $line = &readqline($fp)) {
  }
  
  my %globals = &readconsts($fp);

  foreach my $key (keys(%globals)) {
    if($globals{$key} =~ /\[/ || $globals{$key} =~ /\{/) {
      delete $globals{$key};
    }
  }

  for(my $line = &readqline($fp);
      $line ne 'TURTLES';
      $line = &readqline($fp)) {
  }

  if($args[0] eq 'turtles') {
    my ($headings, $data) = &readsheet($fp);

    close($fp);

    return ($headings, $data);
  }

  for(my $line = &readqline($fp);
      $line ne 'PATCHES';
      $line = &readqline($fp)) {
  }

  if($args[0] eq 'patches') {
    my ($headings, $data) = &readsheet($fp);

    close($fp);

    return ($headings, $data);
  }

  for(my $line = &readqline($fp); $line ne 'LINKS'; $line = &readqline($fp)) {
  }

  if($args[0] eq 'links') {
    my ($headings, $data) = &readsheet($fp);

    close($fp);

    return ($headings, $data);
  }

  for(my $line = &readqline($fp);
      $line ne 'OUTPUT';
      $line = &readqline($fp)) {
  }

  for(my $line = &readqline($fp); $line ne 'PLOTS'; $line = &readqline($fp)) {
  }

  my %plotdata;

  while(&readplot($fp, \%plotdata)) {
  }

  my ($headings, $data) = plotdata2table(%plotdata, $metadata, $netlogo, $date,
					 $file, %globals);

  close($fp);

  return ($headings, $data);
}

sub readplots (*$$) {
  my ($fp, $file, $metadata) = @_;

  my $netlogo = &readqline($fp);
  my $date = &readqline($fp);

  <$fp>;			# Skip blank line

  if(&readqline($fp) ne 'MODEL SETTINGS') {
    # not in a plot
  }

  my %settings = &readconsts($fp);

  my %plotdata;

  <$fp>;			# Skip blank line

  while(&readplot($fp, \%plotdata)) {
  }

  my ($headings, $data) = &plotdata2table(\%plotdata, $metadata, $netlogo,
					  $date, $file, \%settings);

  close($fp);

  return ($headings, $data);
}

sub table2hash ($$) {
  my ($headings, $data) = @_;

  my @hashes;

  foreach my $datum (@$data) {

    my %hash;

    for(my $i = 0; $i <= $#$headings; $i++) {
      $hash{$$headings[$i]} = $$datum[$i];
    }

    push(@hashes, \%hash);
  }

  return \@hashes;
}

sub plotdata2table (\%$$$$\%) {
  my ($plotdata, $metadata, $netlogo, $date, $file, $settings) = @_;

  return ([], []) if $plotdata == 0;

  my $maxstep = 0;

  foreach my $pen (keys(%$plotdata)) {
    if(scalar(@{$plotdata->{$pen}}) > $maxstep) {
      $maxstep = scalar(@{$plotdata->{$pen}});
    }
  }

  my @headings;
  my @data;

  my @penheadings = sort(keys(%$plotdata));

  push(@headings, 'model', 'date', 'file') if $metadata;
  push(@headings, sort(keys(%$settings))) if $metadata;
  push(@headings, 'step');
  push(@headings, @penheadings);

  for(my $step = 0; $step < $maxstep; $step++) {
    my @rowdata;

    if($metadata) {
      push(@rowdata, $netlogo, $date, $file);

      foreach my $key (sort(keys(%$settings))) {
	push(@rowdata, $settings->{$key});
      }
    }

    push(@rowdata, $step);

    for(my $pen = 0; $pen <= $#penheadings; $pen++) {
      if($plotdata->{$penheadings[$pen]}->[$step] =~ /./) {
	push(@rowdata, $plotdata->{$penheadings[$pen]}->[$step]);
      }
      else {
	push(@rowdata, 'NA');
      }
    }

    push(@data, \@rowdata);
  }

  return (\@headings, \@data);
}

sub readplot {
  my ($fp, $data) = @_;

  my $plotname = &readqline($fp);

  return 0 if $plotname !~ /./;
  return 0 if $plotname eq 'EXTENSIONS';

  $plotname =~ s/\"//g;

  my %plotsettings = &readconsts($fp);

  <$fp> or return 0;		# Skip blank line

  my @penheadings = &readcells($fp);

  my @pens;
  for(my $pen = 0; $pen < $plotsettings{'number of pens'}; $pen++) {

    my @cells = &readcells($fp);

    $cells[0] =~ s/\"//g;	# Remove quotes from pen name

    my %pendata;
    for(my $i = 0; $i <= $#penheadings; $i++) {
      $pendata{$penheadings[$i]} = $cells[$i];
    }

    push(@pens, \%pendata);
  }

  <$fp> or return 0;		# Skip blank line

  my $penline = <$fp> or return 0;
  $penline =~ s/\s*\z//;
  $penline =~ s/\"//g;
  my @penlineheadings = split(/,/, $penline);

  my @penstepheadings = &readcells($fp);

  for(my @cells = &readcells($fp);
      scalar(@cells) > 0;
      @cells = &readcells($fp)) {

    for(my $pen = 0; $pen <= $#pens; $pen++) {
      if($pens[$pen]->{'mode'} == 0) {
	my $x = shift(@cells);
	my $y = shift(@cells);
	my $color = shift(@cells);
	my $pendown = shift(@cells);
	my $penname = $pens[$pen]->{'pen name'};

	if($penname ne $penlineheadings[$pen * 4]) {
	  # Pens haven't been listed in the same order
	}

	if(!defined($data->{"$plotname.$penname"})) {
	  $data->{"$plotname.$penname"} = [];
	}

	$data->{"$plotname.$penname"}->[$x] = $y;
      }
    }
  }

  return 1;
}

sub readbspace (*$$) {
  my ($fp, $file, $metadata) = @_;

  my $netlogo = &readqline($fp);
  my $exptid = &readqline($fp);
  my $date = &readqline($fp);

  my %envsize = &readconsts($fp);

  my @cells = &readcells($fp);

  if($cells[0] ne '[run number]') {
    die "Expecting \"[run number]\", found \"$cells[0]\" in netlogo output ",
    "file $file\n";
  }

  if($cells[1] =~ /^\d+$/) {
    shift @cells;
    return readspreadsheet($fp, $file, $metadata, $netlogo, $exptid, $date,
			   \%envsize, \@cells);
  }
  else {
    return readtable($fp, $file, $metadata, $netlogo, $exptid, $date,
		     \%envsize, \@cells);
  }
  
}

sub readtable($$$$$$\%\@) {
  my ($fp, $file, $metadata, $netlogo, $exptid, $date, $envsize, $headings)
    = @_;

  my @headers;

  push(@headers, 'model', 'expt.id', 'date', 'file') if $metadata;
  push(@headers, sort(keys(%$envsize))) if $metadata;

  foreach my $heading (@$headings) {
    $heading = 'run' if $heading eq '[run number]';
    $heading = 'step' if $heading eq '[step]';

    push(@headers, $heading);
  }

  my @data;

  for(my @cells = &readcells($fp);
      scalar(@cells) > 0;
      @cells = &readcells($fp)) {
    
    my @rowdata;

    if($metadata) {
      push(@rowdata, $netlogo, $exptid, $date, $file);

      foreach my $key (sort(keys(%$envsize))) {
	push(@rowdata, $envsize->{$key});
      }
    }

    foreach my $cell (@cells) {
      if($cell =~ /./) {
	push(@rowdata, $cell);
      }
      else {
	push(@rowdata, 'NA');
      }
    }

    push(@data, \@rowdata);
  }

  close($fp);

  return (\@headers, \@data);
}

sub readspreadsheet ($$$$$$\%\@) {
  my ($fp, $file, $metadata, $netlogo, $exptid, $date, $envsize, $runnos) = @_;

  my %params;

  my @cells;

  for(@cells = &readcells($fp);
      $cells[0] ne '[reporter]';
      @cells = &readcells($fp)) {

    my $var = shift(@cells);

    $params{$var} = [ @cells ];
  }

  shift(@cells);
  my @reporters = @cells;

  for(@cells = &readcells($fp);
      $cells[0] ne '[steps]';
      @cells = &readcells($fp)) {
    # Ignore the min/max/etc. summary stats
  }

  shift(@cells);
  my @steps = @cells;

  my $maxstep = 0;

  foreach my $step (@steps) {
    $maxstep = $step if $step > $maxstep;
  }

  <$fp>;			# Skip blank line

  my @reporterheadings = &readcells($fp);

  shift(@reporterheadings);	# Remove '[all run data]'

  my $reps = scalar(@reporterheadings) / scalar(@reporters);

  my @data;
  my @headers;

  push(@headers, 'model', 'expt.id', 'date', 'file') if $metadata;
  push(@headers, sort(keys(%$envsize))) if $metadata;
  push(@headers, sort(keys(%params)));
  push(@headers, 'run', 'step');
  push(@headers, @reporters);

  for(my $step = 0; $step <= $maxstep; $step++) {

    my @cells = &readcells($fp);
    shift(@cells);		# Remove empty initial cell


    for(my $run = 0; $run <= $#$runnos; $run += scalar(@reporters)) {
      my @rowdata;

      if($metadata) {
	push(@rowdata, $netlogo, $exptid, $date, $file);

	foreach my $key (sort(keys(%$envsize))) {
	  push(@rowdata, $envsize->{$key});
	}
      }

      foreach my $key (sort(keys(%params))) {
	push(@rowdata, $params{$key}->[$run]);
      }

      for(my $r = 0; $r <= $#reporters; $r++) {
	push(@rowdata, $$runnos[$run + $r], $step) if $r == 0;

	if($cells[$run + $r] =~ /./) {
	  push(@rowdata, $cells[$run + $r]);
	}
	else {
	  push(@rowdata, 'NA');
	}
      }

      push(@data, \@rowdata);
    }
  }

  close($fp);

  return (\@headers, \@data);
}

sub readconsts {
  my ($fp) = @_;

  my %consts;

  my @names = &readcells($fp);

  my @values = &readcells($fp);

  for(my $i = 0; $i <= $#names; $i++) {
    $consts{$names[$i]} = $values[$i];
  }

  return %consts;
}

sub readqline {
  my ($fp) = @_;

  my $line = <$fp>;
  
  $line =~ s/\s*\z//;

  $line =~ s/^\"//;
  $line =~ s/\"$//;
  $line =~ s/\"\"/\"/g;

  return $line;
}

sub readcells {
  my ($fp) = @_;

  my $line = <$fp>;

  $line =~ s/\s*\z//;

  my @cells = split(/,/, $line, -1);

  for(my $i = 0; $i <= $#cells; $i++) {
    $cells[$i] =~ s/^\"//;
    $cells[$i] =~ s/\"$//;
    $cells[$i] =~ s/\"\"/\"/g;
  }

  return @cells;
}

sub readsheet {
  my ($fp) = @_;

  my @headings = &readcells($fp);
  my @data;

  for(my @cells = &readcells($fp);
      scalar(@cells) == scalar(@headings);
      @cells = &readcells($fp)) {

    push(@data, [ @cells ]);
  }

  return (\@headings, \@data);
}


1;
